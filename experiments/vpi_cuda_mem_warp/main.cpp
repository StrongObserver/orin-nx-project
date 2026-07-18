#include <cuda.h>
#include <cuda_runtime.h>
#include <vpi/Image.h>
#include <vpi/Status.h>
#include <vpi/Stream.h>
#include <vpi/algo/PerspectiveWarp.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

namespace
{

#define CHECK_CUDA(call)                                                                            \
    do                                                                                              \
    {                                                                                               \
        cudaError_t status = (call);                                                                \
        if (status != cudaSuccess)                                                                  \
        {                                                                                           \
            std::cerr << "CUDA error at " << __FILE__ << ":" << __LINE__ << " "                  \
                      << cudaGetErrorString(status) << std::endl;                                   \
            return 1;                                                                               \
        }                                                                                           \
    } while (0)

#define CHECK_VPI(call)                                                                             \
    do                                                                                              \
    {                                                                                               \
        VPIStatus status = (call);                                                                  \
        if (status != VPI_SUCCESS)                                                                  \
        {                                                                                           \
            char buffer[VPI_MAX_STATUS_MESSAGE_LENGTH];                                             \
            vpiGetLastStatusMessage(buffer, sizeof(buffer));                                        \
            std::cerr << "VPI error at " << __FILE__ << ":" << __LINE__ << " status=" << status  \
                      << " message=" << buffer << std::endl;                                       \
            return 1;                                                                               \
        }                                                                                           \
    } while (0)

struct Args
{
    int width = 3840;
    int height = 2160;
    int frames = 200;
    int warmup = 10;
};

Args parse_args(int argc, char **argv)
{
    Args args;
    for (int i = 1; i < argc; ++i)
    {
        std::string key = argv[i];
        auto next_int = [&](int &target) {
            if (i + 1 >= argc)
            {
                std::cerr << "Missing value for " << key << std::endl;
                std::exit(2);
            }
            target = std::atoi(argv[++i]);
        };
        if (key == "--width")
        {
            next_int(args.width);
        }
        else if (key == "--height")
        {
            next_int(args.height);
        }
        else if (key == "--frames")
        {
            next_int(args.frames);
        }
        else if (key == "--warmup")
        {
            next_int(args.warmup);
        }
        else if (key == "--help" || key == "-h")
        {
            std::cout << "vpi_cuda_mem_warp [--width W] [--height H] [--frames N] [--warmup N]\n";
            std::exit(0);
        }
        else
        {
            std::cerr << "Unknown argument: " << key << std::endl;
            std::exit(2);
        }
    }
    return args;
}

void fill_image_data(uint8_t *host, int width, int height, size_t row_bytes)
{
    for (int y = 0; y < height; ++y)
    {
        uint8_t *row = host + y * row_bytes;
        for (int x = 0; x < width; ++x)
        {
            row[x * 4 + 0] = static_cast<uint8_t>(x & 0xFF);
            row[x * 4 + 1] = static_cast<uint8_t>(y & 0xFF);
            row[x * 4 + 2] = static_cast<uint8_t>((x + y) & 0xFF);
            row[x * 4 + 3] = 255;
        }
    }
}

VPIImageData make_cuda_pitch_image_data(void *ptr, int width, int height, int pitch_bytes)
{
    VPIImageData data;
    std::memset(&data, 0, sizeof(data));
    data.bufferType = VPI_IMAGE_BUFFER_CUDA_PITCH_LINEAR;
    data.buffer.pitch.format = VPI_IMAGE_FORMAT_RGBA8;
    data.buffer.pitch.numPlanes = 1;
    data.buffer.pitch.planes[0].data = ptr;
    data.buffer.pitch.planes[0].width = width;
    data.buffer.pitch.planes[0].height = height;
    data.buffer.pitch.planes[0].pitchBytes = pitch_bytes;
    return data;
}

} // namespace

int main(int argc, char **argv)
{
    Args args = parse_args(argc, argv);
    const size_t element_bytes = 4;
    const size_t row_bytes = static_cast<size_t>(args.width) * element_bytes;

    uint8_t *input_dev = nullptr;
    uint8_t *output_dev = nullptr;
    size_t input_pitch = 0;
    size_t output_pitch = 0;
    CHECK_CUDA(cudaMallocPitch(reinterpret_cast<void **>(&input_dev), &input_pitch, row_bytes, args.height));
    CHECK_CUDA(cudaMallocPitch(reinterpret_cast<void **>(&output_dev), &output_pitch, row_bytes, args.height));

    uint8_t *host = static_cast<uint8_t *>(std::malloc(input_pitch * args.height));
    if (!host)
    {
        std::cerr << "host allocation failed" << std::endl;
        return 1;
    }
    fill_image_data(host, args.width, args.height, input_pitch);
    CHECK_CUDA(cudaMemcpy2D(input_dev, input_pitch, host, input_pitch, row_bytes, args.height, cudaMemcpyHostToDevice));
    CHECK_CUDA(cudaMemset2D(output_dev, output_pitch, 0, row_bytes, args.height));

    VPIStream stream = nullptr;
    VPIImage input = nullptr;
    VPIImage output = nullptr;

    CHECK_VPI(vpiStreamCreate(VPI_BACKEND_CUDA, &stream));

    VPIImageData input_data = make_cuda_pitch_image_data(input_dev, args.width, args.height, static_cast<int>(input_pitch));
    VPIImageData output_data = make_cuda_pitch_image_data(output_dev, args.width, args.height, static_cast<int>(output_pitch));
    CHECK_VPI(vpiImageCreateWrapper(&input_data, nullptr, VPI_BACKEND_CUDA, &input));
    CHECK_VPI(vpiImageCreateWrapper(&output_data, nullptr, VPI_BACKEND_CUDA, &output));

    VPIPerspectiveTransform xform = {1.0f, 0.004f, 2.0f, -0.003f, 1.0f, -1.0f, 0.0f, 0.0f, 1.0f};

    double total_ms = 0.0;
    double measured_ms = 0.0;
    int measured_frames = 0;
    for (int i = 0; i < args.frames; ++i)
    {
        auto started = std::chrono::high_resolution_clock::now();
        CHECK_VPI(vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, nullptr, VPI_INTERP_LINEAR,
                                           VPI_BORDER_ZERO, 0));
        CHECK_VPI(vpiStreamSync(stream));
        auto ended = std::chrono::high_resolution_clock::now();
        double elapsed = std::chrono::duration<double, std::milli>(ended - started).count();
        total_ms += elapsed;
        if (i >= args.warmup)
        {
            measured_ms += elapsed;
            measured_frames++;
        }
    }

    std::cout << "width=" << args.width << "\n";
    std::cout << "height=" << args.height << "\n";
    std::cout << "frames=" << args.frames << "\n";
    std::cout << "warmup=" << args.warmup << "\n";
    std::cout << "input_pitch=" << input_pitch << "\n";
    std::cout << "output_pitch=" << output_pitch << "\n";
    std::cout << "avg_submit_sync_ms=" << (args.frames > 0 ? total_ms / args.frames : 0.0) << "\n";
    std::cout << "avg_measured_submit_sync_ms=" << (measured_frames > 0 ? measured_ms / measured_frames : 0.0) << "\n";
    std::cout << "measured_frames=" << measured_frames << "\n";

    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    cudaFree(output_dev);
    cudaFree(input_dev);
    std::free(host);
    return 0;
}
