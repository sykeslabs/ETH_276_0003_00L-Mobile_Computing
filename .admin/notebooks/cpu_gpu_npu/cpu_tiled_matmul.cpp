// FP32 16x16 tiled multiplication, with one or four OpenMP CPU workers.
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <vector>
#include <omp.h>

int main(int argc, char** argv) {
    try {
        if (argc != 6) throw std::runtime_error("Expected n repetitions trials threads directory");
        const int n=std::stoi(argv[1]), repetitions=std::stoi(argv[2]), trials=std::stoi(argv[3]), threads=std::stoi(argv[4]);
        const std::string dir=argv[5];
        if(n<=0 || n>4096 || repetitions<=0 || trials<=0 || (threads!=1 && threads!=4))
            throw std::runtime_error("Invalid benchmark configuration");
        std::vector<float> a(size_t(n)*n), b(a.size()), c(a.size());
        auto read=[&](const char* name, std::vector<float>& values){
            std::ifstream input(dir+name,std::ios::binary);
            if(!input.read(reinterpret_cast<char*>(values.data()),values.size()*sizeof(float)))
                throw std::runtime_error("Cannot read matrix");
        };
        read("/a.bin",a); read("/b.bin",b);
        omp_set_dynamic(0); omp_set_num_threads(threads);
        int actual_threads=0;
        #pragma omp parallel
        {
            #pragma omp single
            actual_threads=omp_get_num_threads();
        }
        const int tile=16, tiles=(n+tile-1)/tile;
        auto run=[&](){
            #pragma omp parallel for schedule(static)
            for(int output=0;output<tiles*tiles;++output){
                const int row=(output/tiles)*tile, col=(output%tiles)*tile;
                const int rows=std::min(tile,n-row), cols=std::min(tile,n-col);
                alignas(64) float sums[16][16]={};
                for(int base=0;base<n;base+=tile){
                    alignas(64) float ta[16][16]={},tb[16][16]={};
                    const int inner=std::min(tile,n-base);
                    for(int i=0;i<rows;++i)
                        for(int k=0;k<inner;++k)ta[i][k]=a[size_t(row+i)*n+base+k];
                    for(int k=0;k<inner;++k)
                        for(int j=0;j<cols;++j)tb[k][j]=b[size_t(base+k)*n+col+j];
                    for(int k=0;k<inner;++k)
                        for(int i=0;i<rows;++i){
                            const float value=ta[i][k];
                            #pragma omp simd
                            for(int j=0;j<cols;++j)sums[i][j]+=value*tb[k][j];
                        }
                }
                for(int i=0;i<rows;++i)
                    for(int j=0;j<cols;++j)c[size_t(row+i)*n+col+j]=sums[i][j];
            }
        };
        run(); // One untimed warm-up.
        std::vector<double> times;
        for(int trial=0;trial<trials;++trial){
            const auto start=std::chrono::steady_clock::now();
            for(int repeat=0;repeat<repetitions;++repeat)run();
            times.push_back(std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count());
        }
        std::ofstream output(dir+"/c.bin",std::ios::binary);
        if(!output.write(reinterpret_cast<const char*>(c.data()),c.size()*sizeof(float)))
            throw std::runtime_error("Cannot write result");
        std::cout<<"{\"actual_threads\":"<<actual_threads<<",\"trial_s\":[";
        for(size_t i=0;i<times.size();++i){if(i)std::cout<<',';std::cout<<std::setprecision(12)<<times[i];}
        std::cout<<"]}\n";
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
