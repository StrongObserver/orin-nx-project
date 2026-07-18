cmake_minimum_required(VERSION 3.10)
project(vpi_cuda_mem_warp LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(CUDA REQUIRED)

include_directories(
    /opt/nvidia/vpi2/include
    /usr/local/cuda/include
)

link_directories(
    /opt/nvidia/vpi2/lib/aarch64-linux-gnu
    /opt/nvidia/vpi2/lib64
    /usr/local/cuda/lib64
)

add_executable(vpi_cuda_mem_warp main.cpp)
target_link_libraries(vpi_cuda_mem_warp PRIVATE nvvpi cuda cudart)
