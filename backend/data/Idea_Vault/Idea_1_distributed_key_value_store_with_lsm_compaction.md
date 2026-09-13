# 📚 Academic Research Grounding: Distributed Key-Value Store with LSM Compaction
*Generated on 2026-09-08 23:40:21 | Sub-Service: Zero-LLM Idea Paper Collector*

> [!NOTE]
> Found **5 peer-reviewed papers** directly matching this concept without AI hallucination.

## 🎯 Curated Papers Matrix

| Rank | Relevance | Title | Year | Citations | Key Mechanisms & Techniques | Links |
| :---: | :---: | :--- | :---: | :---: | :--- | :--- |
| **#1** | **43.9%** | **DFlush: DPU-Offloaded Flush for Disaggregated LSM-based Key-Value Stores** | `2025` | `7` | `DPU-Offloaded`, `LSM-based`, `LSM-KVS`, `DPU` | [DOI Link](https://doi.org/10.1145/3725284) |
| **#2** | **41.2%** | **Rethinking The Compaction Policies in LSM-trees** | `2025` | `9` | `LSM-trees`, `LSM-Tree`, `LSM-tree`, `CPU` | [DOI Link](https://doi.org/10.1145/3725344) |
| **#3** | **27.9%** | **How to Grow an LSM-tree? Towards Bridging the Gap Between Theory and Practice** | `2025` | `5` | `LSM-Tree`, `LSM-tree`, `LSM` | [DOI Link](https://doi.org/10.1145/3725310) |
| **#4** | **25.4%** | **An Overview of the Green Hydrogen Value Chain Technologies and Their Challenges for a Net-Zero Future** | `2025` | `11` | `UK` | [DOI Link](https://doi.org/10.3390/hydrogen6020026) |
| **#5** | **21.4%** | **A Survey of AIOps in the Era of Large Language Models** | `2025` | `42` | `LLM-integrated`, `LLM-based`, `RQ3`, `RQ1` | [DOI Link](https://doi.org/10.1145/3746635) |

---

## 🔬 Detailed Literature Digest

### 1. DFlush: DPU-Offloaded Flush for Disaggregated LSM-based Key-Value Stores (2025)
- **Authors**: Chen Ding, Kai Lü, Quanyi Zhang, Zekun Ye
- **Citations**: 7 | **Relevance Score**: 43.9%
- **DOI**: https://doi.org/10.1145/3725284
- **Concepts**: Computer science, Latency (audio), Associative array, Operating system, Embedded system
- **Extracted Techniques**: `DPU-Offloaded` `LSM-based` `LSM-KVS` `DPU` `CPU` `ANN`

**Abstract:**
> Rapid increase of storage and network bandwidth incurs higher CPU consumption in modern data systems. This phenomenon is particularly evident for log-structured merged key-value stores (LSM-KVS), which rely on resource-intensive background operations to flush and compact disk data. While extensive research has been conducted to reduce the CPU overhead of background compaction, less attention has been paid to background flushing, which can also consume a significant amount of valuable CPU cycles and disrupt CPU caches, ultimately impacting overall performance. In this paper, we propose DFlush, a novel solution that uses DPUs to offload background flush operations to reduce its CPU cost. DPUs are an appealing choice for this goal due to their cost-effectiveness, ease of programming, and widespread deployment. However, their complex hardware architecture requires careful design of both the data and control planes. To fully harness the DPU's capabilities, DFlush decomposes a flush job into fine-grained steps, mapped them to DPU hardware units, and accelerates them through pipeline, data, and channel parallelism, ensuring data-plane efficiency. It also introduces an adaptive control plane that dynamically schedules flush jobs from different LSM-KVS instances based on their priority, reducing write stall and tail latency. Our experiments on a real DPU platform with an industrial-grade LSM-KVS show that DFlush delivers higher throughput, significantly lower tail latency, and saves up to dozens of CPU cores per LSM-KVS server while reducing energy consumption.

---
### 2. Rethinking The Compaction Policies in LSM-trees (2025)
- **Authors**: Hengrui Wang, Jiansheng Qiu, Fangzhou Yuan, Huanchen Zhang
- **Citations**: 9 | **Relevance Score**: 41.2%
- **DOI**: https://doi.org/10.1145/3725344
- **Concepts**: Computer science, Compaction, Workload, Throughput, Merge (version control)
- **Extracted Techniques**: `LSM-trees` `LSM-Tree` `LSM-tree` `CPU` `RA` `WA`

**Abstract:**
> Log-structured merge-trees (LSM-trees) are widely used to construct key-value stores. They periodically compact overlapping sorted runs to reduce the read amplification. Prior research on compaction policies has focused on the trade-off between write amplification (WA) and read amplification (RA). In this paper, we propose to treat the compaction operation in LSM-trees as a computational and I/O-bandwidth investment for improving the system's future query throughput, and thus rethink the compaction policy designs. A typical LSM-tree application handles a steady but moderate write stream and prioritizes resources for top-level flushes of small sorted runs to avoid data loss due to write stalls. The goal of the compaction policy, therefore, is to maintain an optimal number of sorted runs to maximize average query throughput. Because compaction and read operations compete for the CPU and I/O resources from the same pool, we must perform a joint optimization to determine the appropriate timing and aggressiveness of the compaction. We introduce a three-level model of an LSM-tree and propose EcoTune, an algorithm based on dynamic programming to find the optimal compaction policy according to workload characterizations. Our evaluation on RocksDB shows that EcoTune improves the average query throughput by 1.5x to 3x over the leveling policy and by up to 2.5x over the lazy-leveling policy on workloads with range/point query ratios.

---
### 3. How to Grow an LSM-tree? Towards Bridging the Gap Between Theory and Practice (2025)
- **Authors**: Dingheng Mo, Siqiang Luo, Stratos Idreos
- **Citations**: 5 | **Relevance Score**: 27.9%
- **DOI**: https://doi.org/10.1145/3725310
- **Concepts**: Computer science, Scheme (mathematics), Horizontal and vertical, Tree (set theory), Generalization
- **Extracted Techniques**: `LSM-Tree` `LSM-tree` `LSM`

**Abstract:**
> LSM-tree based key-value stores are widely adopted as the data storage backend in modern big data applications. The LSM-tree grows with data ingestion, by either adding levels with fixed level capacities (dubbed as vertical scheme) or increasing level capacities with fixed number of levels (dubbed as horizontal scheme). The vertical scheme leads the trend in recent system designs in RocksDB, LevelDB, and WiredTiger, whereas the horizontal scheme shows a decline in being adopted in the industry. The growth scheme profoundly impacts the LSM system performance in various aspects such as read, write and space costs. This paper attempts to give a new insight into a fundamental design question -- how to grow an LSM-tree to attain more desirable performance? Our analysis highlights the limitations of the vertical scheme in achieving an optimal read-write trade-off and the horizontal scheme in managing space cost effectively. Building on the analysis, we present a novel approach, Vertiorizon, which combines the strengths of both the vertical and horizontal schemes to achieve a superior balance between lookup, update, and space costs. Its adaptive design makes it highly compatible with a wide spectrum of workloads. Compared to the vertical scheme, Vertiorizon significantly improves the read-write performance trade-off. In contrast to the horizontal scheme, Vertiorizon greatly extends the trade-off range by a non-trivial generalization of Bentley and Saxe's theory, while substantially reducing space costs. When integrated with RocksDB, Vertiorizon demonstrates better write performance than the vertical scheme, while incurring about six times less additional space cost compared to the horizontal scheme.

---
### 4. An Overview of the Green Hydrogen Value Chain Technologies and Their Challenges for a Net-Zero Future (2025)
- **Authors**: Shahrouz Nayebossadri, Michael Walsh, Michael Smailes
- **Citations**: 11 | **Relevance Score**: 25.4%
- **DOI**: https://doi.org/10.3390/hydrogen6020026
- **Concepts**: Net (polyhedron), Zero (linguistics), Chain (unit), Value (mathematics), Computer science
- **Extracted Techniques**: `UK`

**Abstract:**
> As hydrogen emerges as a pivotal energy carrier in the global transition towards net-zero emissions, addressing its technological and regulatory challenges is essential for large-scale deployment. The widespread adoption of hydrogen technologies requires extensive research, technical advancements, validation, testing, and certification to ensure their efficiency, reliability, and safety across various applications, including industrial processes, power generation, and transportation. This study provides an overview of key enabling technologies for green hydrogen production and distribution, highlighting the critical challenges that must be overcome to facilitate their widespread adoption. It examines key hydrogen use cases across multiple sectors, analysing their associated technical and infrastructural challenges. The technological advancements required to improve hydrogen production, storage, transportation, and end-use applications are discussed. The development of state-of-the-art testing and validation facilities is also assessed, as these are vital for ensuring safety, performance, and regulatory compliance. This work also reviews some of the ongoing academic and industrial initiatives in the UK aimed at promoting technological innovation, advancing hydrogen expertise, and developing world-class testing infrastructures. This study emphasises the need for stronger, more integrated collaboration between universities, industries, and certifying bodies for building a strong network that promotes knowledge sharing, standardisation, and innovation for expanding hydrogen solutions and creating a sustainable hydrogen economy.

---
### 5. A Survey of AIOps in the Era of Large Language Models (2025)
- **Authors**: Lingzhe Zhang, Tong Jia, Mengxi Jia, Yifan Wu
- **Citations**: 42 | **Relevance Score**: 21.4%
- **DOI**: https://doi.org/10.1145/3746635
- **Concepts**: Computer science, Data science, Programming language
- **Extracted Techniques**: `LLM-integrated` `LLM-based` `RQ3` `RQ1` `RQ2` `RQ4` `IT`

**Abstract:**
> As large language models (LLMs) grow increasingly sophisticated and pervasive, their application to various Artificial Intelligence for IT Operations (AIOps) tasks has garnered significant attention. However, a comprehensive understanding of the impact, potential, and limitations of LLMs in AIOps remains in its infancy. To address this gap, we conducted a detailed survey of LLM4AIOps, focusing on how LLMs can optimize processes and improve outcomes in this domain. We analyzed 183 research articles published between January 2020 and December 2024 to answer four key research questions (RQs). In RQ1, we examine the diverse failure data sources utilized, including advanced LLM-based processing techniques for legacy data and the incorporation of new data sources enabled by LLMs. RQ2 explores the evolution of AIOps tasks, highlighting the emergence of novel tasks and the publication trends across these tasks. RQ3 investigates the various LLM-based methods applied to address AIOps challenges. Finally, RQ4 reviews evaluation methodologies tailored to assess LLM-integrated AIOps approaches. Based on our findings, we discuss the state-of-the-art advancements and trends, identify gaps in existing research, and propose promising directions for future exploration.

---