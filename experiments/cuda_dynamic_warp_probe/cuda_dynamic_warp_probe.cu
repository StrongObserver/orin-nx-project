#include <cuda_runtime.h>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#define CHECK_CUDA(STMT)                                                        \
    do                                                                          \
    {                                                                           \
        cudaError_t status = (STMT);                                             \
        if (status != cudaSuccess)                                               \
        {                                                                       \
            std::ostringstream ss;                                               \
            ss << "CUDA error " << cudaGetErrorString(status) << " at "        \
               << __FILE__ << ":" << __LINE__;                                  \
            throw std::runtime_error(ss.str());                                  \
        }                                                                       \
    } while (0)

struct Options
{
    int width = 640;
    int height = 368;
    int frames = 180;
    std::string mode = "dynamic_affine";
    std::string format = "rgba";
    std::string csv;
    std::string outputPrefix;
};

__constant__ float c_dst_to_src[9];

__device__ unsigned char clamp_u8(float value)
{
    value = fminf(fmaxf(value, 0.0f), 255.0f);
    return static_cast<unsigned char>(value + 0.5f);
}

__global__ void warp_rgba_kernel(const uchar4 *src, uchar4 *dst, int width, int height)
{
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height)
        return;

    float sx = c_dst_to_src[0] * x + c_dst_to_src[1] * y + c_dst_to_src[2];
    float sy = c_dst_to_src[3] * x + c_dst_to_src[4] * y + c_dst_to_src[5];
    float sw = c_dst_to_src[6] * x + c_dst_to_src[7] * y + c_dst_to_src[8];
    sx /= sw;
    sy /= sw;

    uchar4 out = make_uchar4(0, 0, 0, 255);
    if (sx >= 0.0f && sy >= 0.0f && sx <= width - 1 && sy <= height - 1)
    {
        int x0 = min(static_cast<int>(floorf(sx)), width - 1);
        int y0 = min(static_cast<int>(floorf(sy)), height - 1);
        int x1 = min(x0 + 1, width - 1);
        int y1 = min(y0 + 1, height - 1);
        float ax = sx - x0;
        float ay = sy - y0;
        uchar4 p00 = src[y0 * width + x0];
        uchar4 p01 = src[y0 * width + x1];
        uchar4 p10 = src[y1 * width + x0];
        uchar4 p11 = src[y1 * width + x1];
        float w00 = (1.0f - ax) * (1.0f - ay);
        float w01 = ax * (1.0f - ay);
        float w10 = (1.0f - ax) * ay;
        float w11 = ax * ay;
        out.x = clamp_u8(w00 * p00.x + w01 * p01.x + w10 * p10.x + w11 * p11.x);
        out.y = clamp_u8(w00 * p00.y + w01 * p01.y + w10 * p10.y + w11 * p11.y);
        out.z = clamp_u8(w00 * p00.z + w01 * p01.z + w10 * p10.z + w11 * p11.z);
        out.w = 255;
    }
    dst[y * width + x] = out;
}

__global__ void warp_y8_kernel(const unsigned char *src, unsigned char *dst, int width, int height)
{
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height)
        return;

    float sx = c_dst_to_src[0] * x + c_dst_to_src[1] * y + c_dst_to_src[2];
    float sy = c_dst_to_src[3] * x + c_dst_to_src[4] * y + c_dst_to_src[5];
    float sw = c_dst_to_src[6] * x + c_dst_to_src[7] * y + c_dst_to_src[8];
    sx /= sw;
    sy /= sw;

    unsigned char out = 0;
    if (sx >= 0.0f && sy >= 0.0f && sx <= width - 1 && sy <= height - 1)
    {
        int x0 = min(static_cast<int>(floorf(sx)), width - 1);
        int y0 = min(static_cast<int>(floorf(sy)), height - 1);
        int x1 = min(x0 + 1, width - 1);
        int y1 = min(y0 + 1, height - 1);
        float ax = sx - x0;
        float ay = sy - y0;
        unsigned char p00 = src[y0 * width + x0];
        unsigned char p01 = src[y0 * width + x1];
        unsigned char p10 = src[y1 * width + x0];
        unsigned char p11 = src[y1 * width + x1];
        float w00 = (1.0f - ax) * (1.0f - ay);
        float w01 = ax * (1.0f - ay);
        float w10 = (1.0f - ax) * ay;
        float w11 = ax * ay;
        out = clamp_u8(w00 * p00 + w01 * p01 + w10 * p10 + w11 * p11);
    }
    dst[y * width + x] = out;
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
        else if (arg == "--mode")
            opt.mode = needValue("--mode");
        else if (arg == "--format")
            opt.format = needValue("--format");
        else if (arg == "--csv")
            opt.csv = needValue("--csv");
        else if (arg == "--output-prefix")
            opt.outputPrefix = needValue("--output-prefix");
        else
            throw std::runtime_error("unknown argument: " + arg);
    }
    if (opt.csv.empty())
        throw std::runtime_error("--csv is required");
    return opt;
}

static cv::Mat MakeInput(int width, int height)
{
    cv::Mat image(height, width, CV_8UC4);
    for (int y = 0; y < height; ++y)
    {
        for (int x = 0; x < width; ++x)
        {
            image.at<cv::Vec4b>(y, x) = cv::Vec4b(
                static_cast<uint8_t>((x * 255) / std::max(1, width - 1)),
                static_cast<uint8_t>((y * 255) / std::max(1, height - 1)),
                static_cast<uint8_t>(((x + y) * 255) / std::max(1, width + height - 2)),
                255);
        }
    }
    cv::circle(image, cv::Point(width / 3, height / 2), std::max(8, width / 30), cv::Scalar(0, 0, 255, 255), -1);
    cv::rectangle(image, cv::Rect(width / 2, height / 3, width / 5, height / 5), cv::Scalar(255, 255, 255, 255), 2);
    cv::putText(image, "cuda dynamic warp", cv::Point(24, std::max(44, height / 8)),
                cv::FONT_HERSHEY_SIMPLEX, std::max(0.5, width / 1200.0), cv::Scalar(255, 255, 255, 255), 2);
    return image;
}

static cv::Mat MakeInputY(int width, int height)
{
    cv::Mat rgba = MakeInput(width, height);
    cv::Mat gray;
    cv::cvtColor(rgba, gray, cv::COLOR_RGBA2GRAY);
    return gray;
}

static cv::Matx33f SourceToDestMatrix(const Options &opt, int frame)
{
    if (opt.mode == "identity")
        return cv::Matx33f::eye();

    float tx = 24.0f;
    float ty = -12.0f;
    float angleDeg = 3.0f;
    if (opt.mode == "dynamic_affine")
    {
        tx += std::sin(frame * 0.05f) * 4.0f;
        ty += std::cos(frame * 0.04f) * 3.0f;
        angleDeg += std::sin(frame * 0.03f) * 1.5f;
    }
    else if (opt.mode != "static_affine")
    {
        throw std::runtime_error("unsupported mode: " + opt.mode);
    }

    const float angle = angleDeg * static_cast<float>(CV_PI) / 180.0f;
    const float scale = 1.02f;
    const float c = std::cos(angle) * scale;
    const float s = std::sin(angle) * scale;
    const float cx = (opt.width - 1) * 0.5f;
    const float cy = (opt.height - 1) * 0.5f;
    cv::Matx33f t1(1, 0, -cx, 0, 1, -cy, 0, 0, 1);
    cv::Matx33f r(c, -s, 0, s, c, 0, 0, 0, 1);
    cv::Matx33f t2(1, 0, cx + tx, 0, 1, cy + ty, 0, 0, 1);
    return t2 * r * t1;
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

static void CopyMatrixToConstant(const cv::Matx33f &srcToDst)
{
    cv::Matx33f dstToSrc = srcToDst.inv();
    float values[9];
    for (int i = 0; i < 9; ++i)
        values[i] = dstToSrc.val[i];
    CHECK_CUDA(cudaMemcpyToSymbol(c_dst_to_src, values, sizeof(values)));
}

static double MeanAbsDiff(const cv::Mat &a, const cv::Mat &b, double &maxAbs)
{
    cv::Mat diff;
    cv::absdiff(a, b, diff);
    cv::Scalar meanScalar = cv::mean(diff);
    maxAbs = 0.0;
    cv::minMaxLoc(diff.reshape(1), nullptr, &maxAbs);
    return (meanScalar[0] + meanScalar[1] + meanScalar[2]) / 3.0;
}

int main(int argc, char **argv)
{
    try
    {
        Options opt = ParseArgs(argc, argv);
        if (opt.frames <= 0)
            throw std::runtime_error("--frames must be positive");
        const bool useY8 = opt.format == "y8";
        if (!useY8 && opt.format != "rgba")
            throw std::runtime_error("unsupported --format: " + opt.format);
        cv::Mat source = useY8 ? MakeInputY(opt.width, opt.height) : MakeInput(opt.width, opt.height);
        cv::Mat opencvOut;
        cv::Mat cudaOut = useY8 ? cv::Mat(opt.height, opt.width, CV_8UC1) : cv::Mat(opt.height, opt.width, CV_8UC4);

        void *dSrc = nullptr;
        void *dDst = nullptr;
        size_t bytes = static_cast<size_t>(opt.width) * opt.height * (useY8 ? sizeof(unsigned char) : sizeof(uchar4));
        CHECK_CUDA(cudaMalloc(&dSrc, bytes));
        CHECK_CUDA(cudaMalloc(&dDst, bytes));
        CHECK_CUDA(cudaMemcpy(dSrc, source.data, bytes, cudaMemcpyHostToDevice));

        dim3 block(16, 16);
        dim3 grid((opt.width + block.x - 1) / block.x, (opt.height + block.y - 1) / block.y);
        cudaEvent_t startEvent, stopEvent;
        CHECK_CUDA(cudaEventCreate(&startEvent));
        CHECK_CUDA(cudaEventCreate(&stopEvent));

        double matrixUpdateTotalMs = 0.0;
        double kernelTotalMs = 0.0;
        double totalFrameTotalMs = 0.0;
        for (int frame = 0; frame < opt.frames; ++frame)
        {
            auto frameStart = std::chrono::steady_clock::now();
            cv::Matx33f mat = SourceToDestMatrix(opt, frame);
            auto matrixStart = std::chrono::steady_clock::now();
            CopyMatrixToConstant(mat);
            auto matrixEnd = std::chrono::steady_clock::now();
            matrixUpdateTotalMs += std::chrono::duration<double, std::milli>(matrixEnd - matrixStart).count();

            CHECK_CUDA(cudaEventRecord(startEvent));
            if (useY8)
                warp_y8_kernel<<<grid, block>>>(static_cast<unsigned char *>(dSrc), static_cast<unsigned char *>(dDst), opt.width, opt.height);
            else
                warp_rgba_kernel<<<grid, block>>>(static_cast<uchar4 *>(dSrc), static_cast<uchar4 *>(dDst), opt.width, opt.height);
            CHECK_CUDA(cudaEventRecord(stopEvent));
            CHECK_CUDA(cudaEventSynchronize(stopEvent));
            CHECK_CUDA(cudaGetLastError());
            float kernelMs = 0.0f;
            CHECK_CUDA(cudaEventElapsedTime(&kernelMs, startEvent, stopEvent));
            kernelTotalMs += kernelMs;
            auto frameEnd = std::chrono::steady_clock::now();
            totalFrameTotalMs += std::chrono::duration<double, std::milli>(frameEnd - frameStart).count();
        }

        CHECK_CUDA(cudaMemcpy(cudaOut.data, dDst, bytes, cudaMemcpyDeviceToHost));
        cv::Mat mapX(opt.height, opt.width, CV_32FC1);
        cv::Mat mapY(opt.height, opt.width, CV_32FC1);
        FillOpenCVMaps(mapX, mapY, SourceToDestMatrix(opt, opt.frames - 1));
        cv::remap(source, opencvOut, mapX, mapY, cv::INTER_LINEAR, cv::BORDER_CONSTANT, cv::Scalar(0, 0, 0, 255));
        double maxAbs = 0.0;
        double meanAbs = MeanAbsDiff(opencvOut, cudaOut, maxAbs);

        if (!opt.outputPrefix.empty())
        {
            cv::imwrite(opt.outputPrefix + "_source.png", source);
            cv::imwrite(opt.outputPrefix + "_opencv.png", opencvOut);
            cv::imwrite(opt.outputPrefix + "_cuda.png", cudaOut);
            cv::Mat diff;
            cv::absdiff(opencvOut, cudaOut, diff);
            cv::imwrite(opt.outputPrefix + "_absdiff.png", diff);
        }

        std::ofstream csv(opt.csv);
        csv << "status,width,height,format,mode,frames,matrix_update_avg_ms,kernel_avg_ms,total_avg_ms,mean_abs,max_abs\n";
        csv << "pass," << opt.width << "," << opt.height << "," << opt.format << "," << opt.mode << "," << opt.frames << ","
            << matrixUpdateTotalMs / opt.frames << "," << kernelTotalMs / opt.frames << ","
            << totalFrameTotalMs / opt.frames << "," << meanAbs << "," << maxAbs << "\n";

        cudaEventDestroy(stopEvent);
        cudaEventDestroy(startEvent);
        cudaFree(dDst);
        cudaFree(dSrc);
        return 0;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << "\n";
        std::cout << "status,width,height,format,mode,frames,matrix_update_avg_ms,kernel_avg_ms,total_avg_ms,mean_abs,max_abs\n";
        std::cout << "fail,0,0,unknown,unknown,0,0,0,0,0,0\n";
        return 2;
    }
}
