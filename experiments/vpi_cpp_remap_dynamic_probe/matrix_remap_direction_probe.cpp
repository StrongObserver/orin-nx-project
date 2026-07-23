#include <vpi/OpenCVInterop.hpp>
#include <vpi/Image.h>
#include <vpi/Status.h>
#include <vpi/Stream.h>
#include <vpi/WarpMap.h>
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
    int gridInterval = 16;
    std::string matrix = "translate";
    std::string outputPrefix;
    std::string csv;
};

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
        else if (arg == "--grid-interval")
            opt.gridInterval = std::stoi(needValue("--grid-interval"));
        else if (arg == "--matrix")
            opt.matrix = needValue("--matrix");
        else if (arg == "--output-prefix")
            opt.outputPrefix = needValue("--output-prefix");
        else if (arg == "--csv")
            opt.csv = needValue("--csv");
        else
            throw std::runtime_error("unknown argument: " + arg);
    }
    if (opt.outputPrefix.empty())
        throw std::runtime_error("--output-prefix is required");
    if (opt.csv.empty())
        throw std::runtime_error("--csv is required");
    return opt;
}

static int AlignUp(int value, int align)
{
    return ((value + align - 1) / align) * align;
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
    cv::circle(image, cv::Point(width / 3, height / 2), std::max(8, width / 30), cv::Scalar(0, 0, 255), -1);
    cv::rectangle(image, cv::Rect(width / 2, height / 3, width / 5, height / 5), cv::Scalar(255, 255, 255), 2);
    cv::putText(image, "matrix direction", cv::Point(24, std::max(44, height / 8)),
                cv::FONT_HERSHEY_SIMPLEX, std::max(0.5, width / 1200.0), cv::Scalar(255, 255, 255), 2);
    return image;
}

static cv::Matx33f SourceToDestMatrix(const Options &opt)
{
    if (opt.matrix == "identity")
    {
        return cv::Matx33f::eye();
    }
    if (opt.matrix == "translate")
    {
        return cv::Matx33f(1, 0, 24, 0, 1, -12, 0, 0, 1);
    }
    if (opt.matrix == "scale_rotate")
    {
        const float angle = 3.0f * static_cast<float>(CV_PI) / 180.0f;
        const float scale = 1.02f;
        const float c = std::cos(angle) * scale;
        const float s = std::sin(angle) * scale;
        const float cx = (opt.width - 1) * 0.5f;
        const float cy = (opt.height - 1) * 0.5f;
        cv::Matx33f t1(1, 0, -cx, 0, 1, -cy, 0, 0, 1);
        cv::Matx33f r(c, -s, 0, s, c, 0, 0, 0, 1);
        cv::Matx33f t2(1, 0, cx + 8, 0, 1, cy - 4, 0, 0, 1);
        return t2 * r * t1;
    }
    throw std::runtime_error("unsupported matrix: " + opt.matrix);
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

static void FillWarpMapFromOutputToInput(VPIWarpMap &map, const cv::Matx33f &srcToDst)
{
    cv::Matx33f dstToSrc = srcToDst.inv();
    for (int y = 0; y < map.numVertPoints; ++y)
    {
        auto *row = reinterpret_cast<VPIKeypointF32 *>(reinterpret_cast<uint8_t *>(map.keypoints) + y * map.pitchBytes);
        for (int x = 0; x < map.numHorizPoints; ++x)
        {
            float ox = row[x].x;
            float oy = row[x].y;
            cv::Vec3f p = dstToSrc * cv::Vec3f(ox, oy, 1.0f);
            row[x].x = p[0] / p[2];
            row[x].y = p[1] / p[2];
        }
    }
}

static void FillOpenCVMaps(cv::Mat &mapX, cv::Mat &mapY, const cv::Matx33f &srcToDst)
{
    cv::Matx33f dstToSrc = srcToDst.inv();
    for (int y = 0; y < mapX.rows; ++y)
    {
        for (int x = 0; x < mapX.cols; ++x)
        {
            cv::Vec3f p = dstToSrc * cv::Vec3f(static_cast<float>(x), static_cast<float>(y), 1.0f);
            mapX.at<float>(y, x) = p[0] / p[2];
            mapY.at<float>(y, x) = p[1] / p[2];
        }
    }
}

int main(int argc, char **argv)
{
    VPIStream stream = nullptr;
    VPIPayload payload = nullptr;
    VPIImage input = nullptr;
    VPIImage output = nullptr;
    VPIWarpMap map = {};

    try
    {
        Options opt = ParseArgs(argc, argv);
        cv::Mat source = MakeInput(opt.width, opt.height);
        cv::Mat opencvOut;
        cv::Mat vpiOut = cv::Mat::zeros(opt.height, opt.width, CV_8UC3);

        cv::Matx33f srcToDst = SourceToDestMatrix(opt);
        cv::Mat mapX(opt.height, opt.width, CV_32FC1);
        cv::Mat mapY(opt.height, opt.width, CV_32FC1);
        FillOpenCVMaps(mapX, mapY, srcToDst);
        cv::remap(source, opencvOut, mapX, mapY, cv::INTER_LINEAR, cv::BORDER_CONSTANT, cv::Scalar(0, 0, 0));

        InitGrid(map, opt);
        CHECK_STATUS(vpiWarpMapAllocData(&map));
        CHECK_STATUS(vpiWarpMapGenerateIdentity(&map));
        FillWarpMapFromOutputToInput(map, srcToDst);
        CHECK_STATUS(vpiCreateRemap(VPI_BACKEND_CUDA, &map, &payload));
        CHECK_STATUS(vpiStreamCreate(VPI_BACKEND_CUDA, &stream));
        CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(source, VPI_BACKEND_CUDA, &input));
        CHECK_STATUS(vpiImageCreateWrapperOpenCVMat(vpiOut, VPI_BACKEND_CUDA, &output));
        CHECK_STATUS(vpiSubmitRemap(stream, VPI_BACKEND_CUDA, payload, input, output, VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0));
        CHECK_STATUS(vpiStreamSync(stream));

        cv::Mat diff;
        cv::absdiff(opencvOut, vpiOut, diff);
        cv::Scalar meanScalar = cv::mean(diff);
        double meanAbs = (meanScalar[0] + meanScalar[1] + meanScalar[2]) / 3.0;
        double maxAbs = 0.0;
        cv::minMaxLoc(diff.reshape(1), nullptr, &maxAbs);

        cv::imwrite(opt.outputPrefix + "_source.png", source);
        cv::imwrite(opt.outputPrefix + "_opencv.png", opencvOut);
        cv::imwrite(opt.outputPrefix + "_vpi.png", vpiOut);
        cv::imwrite(opt.outputPrefix + "_absdiff.png", diff);

        std::ofstream csv(opt.csv);
        csv << "status,width,height,matrix,grid_interval,mean_abs,max_abs,source,opencv,vpi,absdiff\n";
        csv << "pass," << opt.width << "," << opt.height << "," << opt.matrix << "," << opt.gridInterval << ","
            << meanAbs << "," << maxAbs << "," << opt.outputPrefix << "_source.png,"
            << opt.outputPrefix << "_opencv.png," << opt.outputPrefix << "_vpi.png,"
            << opt.outputPrefix << "_absdiff.png\n";

        vpiImageDestroy(output);
        vpiImageDestroy(input);
        vpiPayloadDestroy(payload);
        vpiStreamDestroy(stream);
        vpiWarpMapFreeData(&map);
        return 0;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << "\n";
        std::cout << "status,width,height,matrix,grid_interval,mean_abs,max_abs,source,opencv,vpi,absdiff\n";
        std::cout << "fail,0,0,unknown,0,0,0,,,,\n";
        vpiImageDestroy(output);
        vpiImageDestroy(input);
        vpiPayloadDestroy(payload);
        vpiStreamDestroy(stream);
        vpiWarpMapFreeData(&map);
        return 2;
    }
}
