#include <vpi/OpenCVInterop.hpp>
#include <vpi/Image.h>
#include <vpi/Status.h>
#include <vpi/Stream.h>
#include <vpi/WarpMap.h>
#include <vpi/algo/ConvertImageFormat.h>
#include <vpi/algo/Remap.h>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

#define CHECK_STATUS(STMT)                                                     \
    do                                                                         \
    {                                                                          \
        VPIStatus status = (STMT);                                             \
        if (status != VPI_SUCCESS)                                             \
        {                                                                      \
            char buffer[VPI_MAX_STATUS_MESSAGE_LENGTH];                        \
            vpiGetLastStatusMessage(buffer, sizeof(buffer));                   \
            std::ostringstream ss;                                             \
            ss << vpiStatusGetName(status) << ": " << buffer;                 \
            throw std::runtime_error(ss.str());                                \
        }                                                                      \
    } while (0)

struct Options
{
    int width = 640;
    int height = 368;
    int frames = 180;
    int gridInterval = 16;
    std::string backend = "cuda";
    std::string mode = "static_payload";
    std::string imageFormat = "bgr8";
    std::string outputCsv;
};

static uint64_t BackendMask(const std::string &backend)
{
    if (backend == "cpu")
        return VPI_BACKEND_CPU;
    if (backend == "cuda")
        return VPI_BACKEND_CUDA;
    throw std::runtime_error("unsupported backend: " + backend);
}

static Options ParseArgs(int argc, char **argv)
{
    Options opt;
    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];
        auto needValue = [&](const char *name) -> std::string {
            if (i + 1 >= argc)
                throw std::runtime_error(std::string("missing value for ") + name);
            return argv[++i];
        };
        if (arg == "--width")
            opt.width = std::stoi(needValue("--width"));
        else if (arg == "--height")
            opt.height = std::stoi(needValue("--height"));
        else if (arg == "--frames")
            opt.frames = std::stoi(needValue("--frames"));
        else if (arg == "--grid-interval")
            opt.gridInterval = std::stoi(needValue("--grid-interval"));
        else if (arg == "--backend")
            opt.backend = needValue("--backend");
        else if (arg == "--mode")
            opt.mode = needValue("--mode");
        else if (arg == "--image-format")
            opt.imageFormat = needValue("--image-format");
        else if (arg == "--csv")
            opt.outputCsv = needValue("--csv");
        else
            throw std::runtime_error("unknown argument: " + arg);
    }
    return opt;
}

static int AlignUp(int value, int align)
{
    return ((value + align - 1) / align) * align;
}

static double MsSince(std::chrono::steady_clock::time_point start, std::chrono::steady_clock::time_point end)
{
    return std::chrono::duration<double, std::milli>(end - start).count();
}

static cv::Mat MakeInput(int width, int height)
{
    cv::Mat image(height, width, CV_8UC3);
    for (int y = 0; y < height; ++y)
    {
        for (int x = 0; x < width; ++x)
        {
            image.at<cv::Vec3b>(y, x) = cv::Vec3b(
                static_cast<uint8_t>((x * 255) / std::max(1, width - 1)),
                static_cast<uint8_t>((y * 255) / std::max(1, height - 1)),
                static_cast<uint8_t>(((x + y) * 255) / std::max(1, width + height - 2)));
        }
    }
    cv::putText(image, "dynamic remap probe", cv::Point(24, std::max(44, height / 8)),
                cv::FONT_HERSHEY_SIMPLEX, std::max(0.5, width / 1200.0), cv::Scalar(255, 255, 255), 2);
    return image;
}

static void InitGrid(VPIWarpMap &map, const Options &opt)
{
    std::memset(&map, 0, sizeof(map));
    map.grid.numHorizRegions = 1;
    map.grid.numVertRegions = 1;
    map.grid.regionWidth[0] = static_cast<int16_t>(std::max(64, AlignUp(opt.width, 64)));
    map.grid.regionHeight[0] = static_cast<int16_t>(std::max(16, AlignUp(opt.height, 16)));
    map.grid.horizInterval[0] = static_cast<int16_t>(opt.gridInterval);
    map.grid.vertInterval[0] = static_cast<int16_t>(opt.gridInterval);
}

static void FillDynamicMap(VPIWarpMap &map, const Options &opt, int frame)
{
    const float amp = std::max(2.0f, opt.width * 0.010f);
    const float phase = frame * 0.12f;
    const float drift = std::sin(frame * 0.05f) * std::max(1.0f, opt.width * 0.003f);
    for (int y = 0; y < map.numVertPoints; ++y)
    {
        auto *row = reinterpret_cast<VPIKeypointF32 *>(reinterpret_cast<uint8_t *>(map.keypoints) + y * map.pitchBytes);
        for (int x = 0; x < map.numHorizPoints; ++x)
        {
            float px = row[x].x;
            float py = row[x].y;
            px += drift + amp * std::sin(py * 2.0f * 3.14159265f / std::max(1, opt.height) + phase);
            row[x].x = px;
            row[x].y = py;
        }
    }
}

static void AllocateAndFillMap(VPIWarpMap &map, const Options &opt, int frame)
{
    InitGrid(map, opt);
    CHECK_STATUS(vpiWarpMapAllocData(&map));
    CHECK_STATUS(vpiWarpMapGenerateIdentity(&map));
    FillDynamicMap(map, opt, frame);
}

int main(int argc, char **argv)
{
    VPIStream stream = nullptr;
    VPIPayload staticPayload = nullptr;
    VPIImage input = nullptr;
    VPIImage output = nullptr;
    VPIWarpMap staticMap = {};

    try
    {
        Options opt = ParseArgs(argc, argv);
        if (opt.frames <= 0)
            throw std::runtime_error("--frames must be positive");

        uint64_t backend = BackendMask(opt.backend);
        cv::Mat bgr = MakeInput(opt.width, opt.height);
        cv::Mat bgrOut = cv::Mat::zeros(opt.height, opt.width, CV_8UC3);

        CHECK_STATUS(vpiStreamCreate(backend, &stream));

        if (opt.imageFormat == "bgr8")
        {
            CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(bgr, backend, &input));
            CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(bgrOut, backend, &output));
        }
        else if (opt.imageFormat == "nv12_er")
        {
            VPIImage wrappedBGR = nullptr;
            CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(bgr, backend, &wrappedBGR));
            CHECK_STATUS(vpiImageCreate(opt.width, opt.height, VPI_IMAGE_FORMAT_NV12_ER, backend, &input));
            CHECK_STATUS(vpiImageCreate(opt.width, opt.height, VPI_IMAGE_FORMAT_NV12_ER, backend, &output));
            CHECK_STATUS(vpiSubmitConvertImageFormat(stream, backend, wrappedBGR, input, nullptr));
            CHECK_STATUS(vpiStreamSync(stream));
            vpiImageDestroy(wrappedBGR);
        }
        else
        {
            throw std::runtime_error("unsupported image format: " + opt.imageFormat);
        }

        const bool staticPayloadMode = opt.mode == "static_payload";
        const bool dynamicRecreateMode = opt.mode == "dynamic_recreate_payload";
        if (!staticPayloadMode && !dynamicRecreateMode)
            throw std::runtime_error("unsupported mode: " + opt.mode);

        double staticMapBuildMs = 0.0;
        double staticPayloadCreateMs = 0.0;
        if (staticPayloadMode)
        {
            auto mapStart = std::chrono::steady_clock::now();
            AllocateAndFillMap(staticMap, opt, 0);
            auto mapEnd = std::chrono::steady_clock::now();
            auto payloadStart = std::chrono::steady_clock::now();
            CHECK_STATUS(vpiCreateRemap(backend, &staticMap, &staticPayload));
            auto payloadEnd = std::chrono::steady_clock::now();
            staticMapBuildMs = MsSince(mapStart, mapEnd);
            staticPayloadCreateMs = MsSince(payloadStart, payloadEnd);
        }

        double mapBuildTotalMs = 0.0;
        double payloadCreateTotalMs = 0.0;
        double submitSyncTotalMs = 0.0;
        double payloadDestroyTotalMs = 0.0;
        double totalFrameTotalMs = 0.0;

        for (int frame = 0; frame < opt.frames; ++frame)
        {
            auto frameStart = std::chrono::steady_clock::now();
            VPIPayload payload = staticPayload;
            VPIWarpMap dynamicMap = {};

            if (dynamicRecreateMode)
            {
                auto mapStart = std::chrono::steady_clock::now();
                AllocateAndFillMap(dynamicMap, opt, frame);
                auto mapEnd = std::chrono::steady_clock::now();
                auto payloadStart = std::chrono::steady_clock::now();
                CHECK_STATUS(vpiCreateRemap(backend, &dynamicMap, &payload));
                auto payloadEnd = std::chrono::steady_clock::now();
                mapBuildTotalMs += MsSince(mapStart, mapEnd);
                payloadCreateTotalMs += MsSince(payloadStart, payloadEnd);
            }

            auto submitStart = std::chrono::steady_clock::now();
            CHECK_STATUS(vpiSubmitRemap(stream, backend, payload, input, output, VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0));
            CHECK_STATUS(vpiStreamSync(stream));
            auto submitEnd = std::chrono::steady_clock::now();
            submitSyncTotalMs += MsSince(submitStart, submitEnd);

            if (dynamicRecreateMode)
            {
                auto destroyStart = std::chrono::steady_clock::now();
                vpiPayloadDestroy(payload);
                auto destroyEnd = std::chrono::steady_clock::now();
                vpiWarpMapFreeData(&dynamicMap);
                payloadDestroyTotalMs += MsSince(destroyStart, destroyEnd);
            }
            auto frameEnd = std::chrono::steady_clock::now();
            totalFrameTotalMs += MsSince(frameStart, frameEnd);
        }

        double denom = static_cast<double>(opt.frames);
        double mapAvg = dynamicRecreateMode ? mapBuildTotalMs / denom : staticMapBuildMs / denom;
        double payloadCreateAvg = dynamicRecreateMode ? payloadCreateTotalMs / denom : staticPayloadCreateMs / denom;
        double payloadDestroyAvg = dynamicRecreateMode ? payloadDestroyTotalMs / denom : 0.0;
        double submitSyncAvg = submitSyncTotalMs / denom;
        double totalAvg = totalFrameTotalMs / denom;

        std::ostream *out = &std::cout;
        std::ofstream csv;
        if (!opt.outputCsv.empty())
        {
            csv.open(opt.outputCsv);
            out = &csv;
        }
        *out << "status,backend,width,height,image_format,mode,frames,grid_interval,"
             << "map_build_avg_ms,payload_create_avg_ms,submit_sync_avg_ms,payload_destroy_avg_ms,total_avg_ms\n";
        *out << "pass," << opt.backend << "," << opt.width << "," << opt.height << "," << opt.imageFormat << ","
             << opt.mode << "," << opt.frames << "," << opt.gridInterval << ","
             << mapAvg << "," << payloadCreateAvg << "," << submitSyncAvg << "," << payloadDestroyAvg << ","
             << totalAvg << "\n";

        if (staticPayload)
            vpiPayloadDestroy(staticPayload);
        vpiWarpMapFreeData(&staticMap);
        vpiImageDestroy(output);
        vpiImageDestroy(input);
        vpiStreamDestroy(stream);
        return 0;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << "\n";
        std::cout << "status,backend,width,height,image_format,mode,frames,grid_interval,"
                  << "map_build_avg_ms,payload_create_avg_ms,submit_sync_avg_ms,payload_destroy_avg_ms,total_avg_ms\n";
        std::cout << "fail,unknown,0,0,unknown,unknown,0,0,0,0,0,0,0\n";
        vpiPayloadDestroy(staticPayload);
        vpiWarpMapFreeData(&staticMap);
        vpiImageDestroy(output);
        vpiImageDestroy(input);
        vpiStreamDestroy(stream);
        return 2;
    }
}
