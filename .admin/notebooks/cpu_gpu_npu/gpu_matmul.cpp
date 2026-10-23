// Headless Vulkan matrix benchmark. Inputs and reference validation live in gpu_worker.py.
#include <vulkan/vulkan.h>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

void check(VkResult r) { if (r != VK_SUCCESS) throw std::runtime_error("Vulkan error " + std::to_string(r)); }
std::vector<char> read_file(const std::string& name) {
    std::ifstream f(name, std::ios::binary | std::ios::ate);
    if (!f) throw std::runtime_error("Cannot read " + name);
    auto bytes=f.tellg();
    if (bytes<=0) throw std::runtime_error("Empty file " + name);
    std::vector<char> data(static_cast<size_t>(bytes));
    f.seekg(0); f.read(data.data(), data.size());
    if (!f) throw std::runtime_error("Incomplete read " + name);
    return data;
}
int main(int argc, char** argv) {
  try {
    if (argc!=5) throw std::runtime_error("Usage: gpu_matmul N repetitions trials directory");
    uint32_t n=std::stoul(argv[1]), repeats=std::stoul(argv[2]), trials=std::stoul(argv[3]);
    if (!n || n>4096 || !repeats || !trials) throw std::runtime_error("Invalid dimensions or trial counts");
    std::string dir=argv[4];
    VkDeviceSize size=VkDeviceSize(n)*n*sizeof(float);
    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName="CPU GPU NPU notebook"; app.apiVersion=VK_API_VERSION_1_1;
    VkInstanceCreateInfo ici{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&app;
    VkInstance instance; check(vkCreateInstance(&ici,nullptr,&instance));
    uint32_t count=0; check(vkEnumeratePhysicalDevices(instance,&count,nullptr));
    std::vector<VkPhysicalDevice> devices(count); check(vkEnumeratePhysicalDevices(instance,&count,devices.data()));
    VkPhysicalDevice physical=VK_NULL_HANDLE; VkPhysicalDeviceProperties props{};
    for (auto candidate:devices) {
        VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(candidate,&p);
        // Select Broadcom hardware explicitly; never benchmark llvmpipe as a GPU.
        if (p.vendorID==0x14e4 && p.deviceType==VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU) {
            physical=candidate; props=p; break;
        }
    }
    if (!physical) throw std::runtime_error("Broadcom integrated Vulkan GPU not found; software fallback rejected");
    if (props.limits.maxComputeWorkGroupInvocations<256 || props.limits.maxComputeWorkGroupSize[0]<16 ||
        props.limits.maxComputeWorkGroupSize[1]<16 || size>props.limits.maxStorageBufferRange)
        throw std::runtime_error("GPU limits do not support the requested matrix workload");
    vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,nullptr);
    std::vector<VkQueueFamilyProperties> families(count); vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,families.data());
    uint32_t family=UINT32_MAX;
    for(uint32_t i=0;i<count;i++) if(families[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {family=i;break;}
    if(family==UINT32_MAX) throw std::runtime_error("No compute queue");
    float priority=1;
    VkDeviceQueueCreateInfo qci{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    qci.queueFamilyIndex=family; qci.queueCount=1; qci.pQueuePriorities=&priority;
    VkDeviceCreateInfo dci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; dci.queueCreateInfoCount=1; dci.pQueueCreateInfos=&qci;
    VkDevice device; check(vkCreateDevice(physical,&dci,nullptr,&device));
    VkQueue queue; vkGetDeviceQueue(device,family,0,&queue);
    VkPhysicalDeviceMemoryProperties memoryProps; vkGetPhysicalDeviceMemoryProperties(physical,&memoryProps);
    VkBuffer buffers[3]{}; VkDeviceMemory memory[3]{}; void* mapped[3]{};
    for(int i=0;i<3;i++) {
        VkBufferCreateInfo bci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        bci.size=size; bci.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT; bci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        check(vkCreateBuffer(device,&bci,nullptr,&buffers[i]));
        VkMemoryRequirements req; vkGetBufferMemoryRequirements(device,buffers[i],&req);
        uint32_t type=UINT32_MAX;
        auto flags=VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        for(uint32_t m=0;m<memoryProps.memoryTypeCount;m++)
            if((req.memoryTypeBits & (1u<<m)) && (memoryProps.memoryTypes[m].propertyFlags & flags)==flags) {type=m;break;}
        if(type==UINT32_MAX) throw std::runtime_error("No coherent host-visible memory for shared Pi buffers");
        VkMemoryAllocateInfo alloc{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; alloc.allocationSize=req.size; alloc.memoryTypeIndex=type;
        check(vkAllocateMemory(device,&alloc,nullptr,&memory[i]));
        check(vkBindBufferMemory(device,buffers[i],memory[i],0));
        check(vkMapMemory(device,memory[i],0,size,0,&mapped[i]));
    }
    for(int i=0;i<2;i++) {
        auto data=read_file(dir+(i==0?"/a.bin":"/b.bin"));
        if(data.size()!=size) throw std::runtime_error("Input size mismatch");
        std::memcpy(mapped[i],data.data(),size);
    }
    VkDescriptorSetLayoutBinding bindings[3]{};
    for(int i=0;i<3;i++) {bindings[i].binding=i;bindings[i].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        bindings[i].descriptorCount=1;bindings[i].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;}
    VkDescriptorSetLayoutCreateInfo slci{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};slci.bindingCount=3;slci.pBindings=bindings;
    VkDescriptorSetLayout layout;check(vkCreateDescriptorSetLayout(device,&slci,nullptr,&layout));
    VkPushConstantRange push{VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(n)};
    VkPipelineLayoutCreateInfo plci{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    plci.setLayoutCount=1;plci.pSetLayouts=&layout;plci.pushConstantRangeCount=1;plci.pPushConstantRanges=&push;
    VkPipelineLayout pipelineLayout;check(vkCreatePipelineLayout(device,&plci,nullptr,&pipelineLayout));
    auto shaderBytes=read_file(dir+"/matmul.spv");
    if(shaderBytes.size()%4) throw std::runtime_error("Invalid SPIR-V size");
    std::vector<uint32_t> shaderCode(shaderBytes.size()/4);std::memcpy(shaderCode.data(),shaderBytes.data(),shaderBytes.size());
    VkShaderModuleCreateInfo smci{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};smci.codeSize=shaderBytes.size();smci.pCode=shaderCode.data();
    VkShaderModule shader;check(vkCreateShaderModule(device,&smci,nullptr,&shader));
    VkComputePipelineCreateInfo cpci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
    cpci.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;cpci.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;
    cpci.stage.module=shader;cpci.stage.pName="main";cpci.layout=pipelineLayout;
    VkPipeline pipeline;check(vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&cpci,nullptr,&pipeline));
    VkDescriptorPoolSize poolSize{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,3};
    VkDescriptorPoolCreateInfo dpci{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};dpci.maxSets=1;dpci.poolSizeCount=1;dpci.pPoolSizes=&poolSize;
    VkDescriptorPool pool;check(vkCreateDescriptorPool(device,&dpci,nullptr,&pool));
    VkDescriptorSetAllocateInfo dsai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};dsai.descriptorPool=pool;dsai.descriptorSetCount=1;dsai.pSetLayouts=&layout;
    VkDescriptorSet set;check(vkAllocateDescriptorSets(device,&dsai,&set));
    VkDescriptorBufferInfo infos[3]{};VkWriteDescriptorSet writes[3]{};
    for(int i=0;i<3;i++) {infos[i]={buffers[i],0,size};writes[i].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[i].dstSet=set;writes[i].dstBinding=i;writes[i].descriptorCount=1;
        writes[i].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;writes[i].pBufferInfo=&infos[i];}
    vkUpdateDescriptorSets(device,3,writes,0,nullptr);
    VkCommandPoolCreateInfo poolInfo{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};poolInfo.queueFamilyIndex=family;
    VkCommandPool commandPool;check(vkCreateCommandPool(device,&poolInfo,nullptr,&commandPool));
    VkCommandBufferAllocateInfo cbai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};cbai.commandPool=commandPool;
    cbai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;cbai.commandBufferCount=1;
    VkCommandBuffer command;check(vkAllocateCommandBuffers(device,&cbai,&command));
    VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};check(vkBeginCommandBuffer(command,&begin));
    VkMemoryBarrier before{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
    before.srcAccessMask=VK_ACCESS_HOST_WRITE_BIT | VK_ACCESS_SHADER_WRITE_BIT;
    before.dstAccessMask=VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT;
    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_HOST_BIT | VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,1,&before,0,nullptr,0,nullptr);
    vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);
    vkCmdBindDescriptorSets(command,VK_PIPELINE_BIND_POINT_COMPUTE,pipelineLayout,0,1,&set,0,nullptr);
    vkCmdPushConstants(command,pipelineLayout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(n),&n);
    vkCmdDispatch(command,(n+15)/16,(n+15)/16,1);
    VkMemoryBarrier after{VK_STRUCTURE_TYPE_MEMORY_BARRIER};after.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;after.dstAccessMask=VK_ACCESS_HOST_READ_BIT;
    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&after,0,nullptr,0,nullptr);
    check(vkEndCommandBuffer(command));
    VkFenceCreateInfo fci{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VkFence fence;check(vkCreateFence(device,&fci,nullptr,&fence));
    VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&command;
    auto run=[&](){check(vkResetFences(device,1,&fence));check(vkQueueSubmit(queue,1,&submit,fence));
                  check(vkWaitForFences(device,1,&fence,VK_TRUE,60ull*1000000000));};
    run(); // One untimed warm-up.
    std::vector<double> elapsed;
    for(uint32_t t=0;t<trials;t++) {
        auto start=std::chrono::steady_clock::now();
        for(uint32_t r=0;r<repeats;r++)run();
        elapsed.push_back(std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count());
    }
    std::ofstream output(dir+"/c.bin",std::ios::binary);output.write(static_cast<char*>(mapped[2]),size);
    if(!output)throw std::runtime_error("Cannot save GPU output");output.close();
    std::cout<<"{\"device\":"<<std::quoted(props.deviceName)<<",\"vendor_id\":"<<props.vendorID
             <<",\"driver_version\":"<<props.driverVersion<<",\"api_version\":"<<props.apiVersion<<",\"trial_s\":[";
    for(size_t i=0;i<elapsed.size();i++){if(i)std::cout<<",";std::cout<<std::setprecision(12)<<elapsed[i];}
    std::cout<<"]}"<<std::endl;
    check(vkDeviceWaitIdle(device));
    vkDestroyFence(device,fence,nullptr);vkDestroyCommandPool(device,commandPool,nullptr);
    vkDestroyDescriptorPool(device,pool,nullptr);vkDestroyPipeline(device,pipeline,nullptr);
    vkDestroyShaderModule(device,shader,nullptr);vkDestroyPipelineLayout(device,pipelineLayout,nullptr);
    vkDestroyDescriptorSetLayout(device,layout,nullptr);
    for(int i=0;i<3;i++){vkUnmapMemory(device,memory[i]);vkDestroyBuffer(device,buffers[i],nullptr);vkFreeMemory(device,memory[i],nullptr);}
    vkDestroyDevice(device,nullptr);vkDestroyInstance(instance,nullptr);
    return 0;
  } catch(const std::exception& e) {std::cerr<<e.what()<<std::endl;return 1;}
}
