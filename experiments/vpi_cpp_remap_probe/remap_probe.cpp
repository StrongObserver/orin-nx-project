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
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

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
    int height = 360;
    int iterations = 100;
    int gridInterval = 16;
    std::string backend = "cuda";
    std::string mode = "identity";
    std::string imageFormat = "bgr8";
    bool opencvOnly = false;
    std::string output;
    std::string csv;
};

static uint64_t BackendMask(const std::string &backend)
{
    if (backend == "cpu")
        return VPI_BACKEND_CPU;
    if (backend == "cuda")
        return VPI_BACKEND_CUDA;
    if (backend == "vic")
        return VPI_BACKEND_VIC;
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
        else if (arg == "--iterations")
            opt.iterations = std::stoi(needValue("--iterations"));
        else if (arg == "--grid-interval")
            opt.gridInterval = std::stoi(needValue("--grid-interval"));
        else if (arg == "--backend")
            opt.backend = needValue("--backend");
        else if (arg == "--mode")
            opt.mode = needValue("--mode");
        else if (arg == "--image-format")
            opt.imageFormat = needValue("--image-format");
        else if (arg == "--opencv-only")
            opt.opencvOnly = true;
        else if (arg == "--output")
            opt.output = needValue("--output");
        else if (arg == "--csv")
            opt.csv = needValue("--csv");
        else
            throw std::runtime_error("unknown argument: " + arg);
    }
    return opt;
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
    cv::putText(image, "VPI Remap C++ probe", cv::Point(30, std::max(50, height / 8)),
                cv::FONT_HERSHEY_SIMPLEX, std::max(0.5, width / 1200.0), cv::Scalar(255, 255, 255), 2);
    return image;
}

static int AlignUp(int value, int align)
{
    return ((value + align - 1) / align) * align;
}

static void InitWarpMap(VPIWarpMap &map, const Options &opt)
{
    std::memset(&map, 0, sizeof(map));
    map.grid.numHorizRegions = 1;
    map.grid.numVertRegions = 1;
    map.grid.regionWidth[0] = static_cast<int16_t>(std::max(64, AlignUp(opt.width, 64)));
    map.grid.regionHeight[0] = static_cast<int16_t>(std::max(16, AlignUp(opt.height, 16)));
    map.grid.horizInterval[0] = static_cast<int16_t>(opt.gridInterval);
    map.grid.vertInterval[0] = static_cast<int16_t>(opt.gridInterval);
    CHECK_STATUS(vpiWarpMapAllocData(&map));
    CHECK_STATUS(vpiWarpMapGenerateIdentity(&map));

    const float cx = (opt.width - 1) * 0.5f;
    const float cy = (opt.height - 1) * 0.5f;
    const float shiftX = std::max(4.0f, opt.width * 0.02f);
    const float amp = std::max(3.0f, opt.width * 0.015f);

    for (int y = 0; y < map.numVertPoints; ++y)
    {
        auto *row = reinterpret_cast<VPIKeypointF32 *>(reinterpret_cast<uint8_t *>(map.keypoints) + y * map.pitchBytes);
        for (int x = 0; x < map.numHorizPoints; ++x)
        {
            float px = row[x].x;
            float py = row[x].y;
            if (opt.mode == "shift")
            {
                px = px + shiftX;
            }
            else if (opt.mode == "wave")
            {
                px = px + amp * std::sin(py * 2.0f * 3.14159265f / std::max(1, opt.height));
            }
            else if (opt.mode == "pinch")
            {
                float dx = px - cx;
                float dy = py - cy;
                float r2 = (dx * dx + dy * dy) / std::max(1.0f, cx * cx + cy * cy);
                float scale = 1.0f + 0.08f * std::exp(-4.0f * r2);
                px = cx + dx * scale;
                py = cy + dy * scale;
            }
            else if (opt.mode != "identity")
            {
                throw std::runtime_error("unsupported mode: " + opt.mode);
            }
            row[x].x = px;
            row[x].y = py;
        }
    }
}

static double MsSince(std::chrono::steady_clock::time_point start, std::chrono::steady_clock::time_point end)
{
    return std::chrono::duration<double, std::milli>(end - start).count();
}

static void FillOpenCVMaps(cv::Mat &mapX, cv::Mat &mapY, const Options &opt)
{
    const float cx = (opt.width - 1) * 0.5f;
    const float cy = (opt.height - 1) * 0.5f;
    const float shiftX = std::max(4.0f, opt.width * 0.02f);
    const float amp = std::max(3.0f, opt.width * 0.015f);
    for (int y = 0; y < opt.height; ++y)
    {
        for (int x = 0; x < opt.width; ++x)
        {
            float px = static_cast<float>(x);
            float py = static_cast<float>(y);
            if (opt.mode == "shift")
            {
                px += shiftX;
            }
            else if (opt.mode == "wave")
            {
                px += amp * std::sin(py * 2.0f * 3.14159265f / std::max(1, opt.height));
            }
            else if (opt.mode == "pinch")
            {
                float dx = px - cx;
                float dy = py - cy;
                float r2 = (dx * dx + dy * dy) / std::max(1.0f, cx * cx + cy * cy);
                float scale = 1.0f + 0.08f * std::exp(-4.0f * r2);
                px = cx + dx * scale;
                py = cy + dy * scale;
            }
            mapX.at<float>(y, x) = px;
            mapY.at<float>(y, x) = py;
        }
    }
}

int main(int argc, char **argv)
{
    VPIStream stream = nullptr;
    VPIPayload payload = nullptr;
    VPIImage wrappedInput = nullptr;
    VPIImage wrappedOutput = nullptr;
    VPIWarpMap map = {};

    try
    {
        Options opt = ParseArgs(argc, argv);

        cv::Mat bgr = MakeInput(opt.width, opt.height);
        cv::Mat output = cv::Mat::zeros(opt.height, opt.width, CV_8UC3);

        if (opt.opencvOnly)
        {
            cv::Mat mapX(opt.height, opt.width, CV_32FC1);
            cv::Mat mapY(opt.height, opt.width, CV_32FC1);
            FillOpenCVMaps(mapX, mapY, opt);
            double totalMs = 0.0;
            for (int i = 0; i < opt.iterations; ++i)
            {
                auto start = std::chrono::steady_clock::now();
                cv::remap(bgr, output, mapX, mapY, cv::INTER_LINEAR, cv::BORDER_CONSTANT, cv::Scalar(0, 0, 0));
                auto end = std::chrono::steady_clock::now();
                totalMs += MsSince(start, end);
            }
            if (!opt.output.empty())
            {
                cv::imwrite(opt.output, output);
            }
            double avgMs = totalMs / std::max(1, opt.iterations);
            std::cout << "status,backend,width,height,mode,image_format,grid_interval,iterations,avg_remap_ms\n";
            std::cout << "pass,opencv_cpu," << opt.width << "," << opt.height << "," << opt.mode << ",bgr8,0,"
                      << opt.iterations << "," << avgMs << "\n";
            if (!opt.csv.empty())
            {
                std::ofstream csv(opt.csv);
                csv << "status,backend,width,height,mode,image_format,grid_interval,iterations,avg_remap_ms\n";
                csv << "pass,opencv_cpu," << opt.width << "," << opt.height << "," << opt.mode << ",bgr8,0,"
                    << opt.iterations << "," << avgMs << "\n";
            }
            return 0;
        }

        uint64_t backend = BackendMask(opt.backend);

        InitWarpMap(map, opt);
        CHECK_STATUS(vpiCreateRemap(backend, &map, &payload));
        CHECK_STATUS(vpiStreamCreate(backend, &stream));

        if (opt.imageFormat == "bgr8")
        {
            CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(bgr, backend, &wrappedInput));
            CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(output, backend, &wrappedOutput));
        }
        else if (opt.imageFormat == "nv12_er")
        {
            VPIImage wrappedBGR = nullptr;
            CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(bgr, backend, &wrappedBGR));
            CHECK_STATUS(vpiImageCreate(opt.width, opt.height, VPI_IMAGE_FORMAT_NV12_ER, backend, &wrappedInput));
            CHECK_STATUS(vpiImageCreate(opt.width, opt.height, VPI_IMAGE_FORMAT_NV12_ER, backend, &wrappedOutput));
            CHECK_STATUS(vpiSubmitConvertImageFormat(stream, backend, wrappedBGR, wrappedInput, nullptr));
            CHECK_STATUS(vpiStreamSync(stream));
            vpiImageDestroy(wrappedBGR);
        }
        else
        {
            throw std::runtime_error("unsupported image format: " + opt.imageFormat);
        }

        double totalMs = 0.0;
        for (int i = 0; i < opt.iterations; ++i)
        {
            auto start = std::chrono::steady_clock::now();
            CHECK_STATUS(vpiSubmitRemap(stream, backend, payload, wrappedInput, wrappedOutput, VPI_INTERP_LINEAR,
                                        VPI_BORDER_ZERO, 0));
            CHECK_STATUS(vpiStreamSync(stream));
            auto end = std::chrono::steady_clock::now();
            totalMs += MsSince(start, end);
        }

        if (!opt.output.empty())
        {
            cv::imwrite(opt.output, output);
        }

        double avgMs = totalMs / std::max(1, opt.iterations);
        std::cout << "status,backend,width,height,mode,image_format,grid_interval,iterations,avg_remap_ms\n";
        std::cout << "pass," << opt.backend << "," << opt.width << "," << opt.height << "," << opt.mode << ","
                  << opt.imageFormat << "," << opt.gridInterval << "," << opt.iterations << "," << avgMs << "\n";

        if (!opt.csv.empty())
        {
            std::ofstream csv(opt.csv);
            csv << "status,backend,width,height,mode,image_format,grid_interval,iterations,avg_remap_ms\n";
            csv << "pass," << opt.backend << "," << opt.width << "," << opt.height << "," << opt.mode << ","
                << opt.imageFormat << "," << opt.gridInterval << "," << opt.iterations << "," << avgMs << "\n";
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << "\n";
        std::cout << "status,backend,width,height,mode,image_format,grid_interval,iterations,avg_remap_ms\n";
        std::cout << "fail,unknown,0,0,unknown,unknown,0,0,\n";
        vpiWarpMapFreeData(&map);
        vpiImageDestroy(wrappedOutput);
        vpiImageDestroy(wrappedInput);
        vpiPayloadDestroy(payload);
        vpiStreamDestroy(stream);
        return 2;
    }

    vpiWarpMapFreeData(&map);
    vpiImageDestroy(wrappedOutput);
    vpiImageDestroy(wrappedInput);
    vpiPayloadDestroy(payload);
    vpiStreamDestroy(stream);
    return 0;
}
