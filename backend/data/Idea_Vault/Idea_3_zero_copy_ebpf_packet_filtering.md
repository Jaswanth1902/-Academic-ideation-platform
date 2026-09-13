# 📚 Academic Research Grounding: Zero-Copy eBPF Packet Filtering
*Generated on 2026-09-08 23:51:48 | Sub-Service: Zero-LLM Idea Paper Collector*

> [!NOTE]
> Found **3 peer-reviewed papers** directly matching this concept without AI hallucination.

## 🎯 Curated Papers Matrix

| Rank | Relevance | Title | Year | Citations | Key Mechanisms & Techniques | Links |
| :---: | :---: | :--- | :---: | :---: | :--- | :--- |
| **#1** | **28.8%** | **High-Speed Network DDoS Attack Detection: A Survey** | `2023` | `34` | `Nearest Neighbor`, `HSN`, `KNN`, `CPS` | [DOI Link](https://doi.org/10.3390/s23156850) |
| **#2** | **23.0%** | **Demystifying Performance of eBPF Network Applications** | `2025` | `6` | `eBPF`, `ANN` | [DOI Link](https://doi.org/10.1145/3749216) |
| **#3** | **18.5%** | **Empowering Cloud Computing With Network Acceleration: A Survey** | `2024` | `41` | `DPDK`, `RDMA`, `XDP` | [DOI Link](https://doi.org/10.1109/comst.2024.3377531) |

---

## 🔬 Detailed Literature Digest

### 1. High-Speed Network DDoS Attack Detection: A Survey (2023)
- **Authors**: Rana Muhammad Abdul Haseeb-ur-rehman, Azana Hafizah Mohd Aman, Mohammad Kamrul Hasan, Khairul Akram Zainol Ariffin
- **Citations**: 34 | **Relevance Score**: 28.8%
- **DOI**: https://doi.org/10.3390/s23156850
- **Concepts**: Denial-of-service attack, Computer science, Network packet, Intrusion detection system, Naive Bayes classifier
- **Extracted Techniques**: `Nearest Neighbor` `HSN` `KNN` `CPS` `ML` `NB`

**Abstract:**
> Having a large number of device connections provides attackers with multiple ways to attack a network. This situation can lead to distributed denial-of-service (DDoS) attacks, which can cause fiscal harm and corrupt data. Thus, irregularity detection in traffic data is crucial in detecting malicious behavior in a network, which is essential for network security and the integrity of modern Cyber-Physical Systems (CPS). Nevertheless, studies have shown that current techniques are ineffective at detecting DDoS attacks on networks, especially in the case of high-speed networks (HSN), as detecting attacks on the latter is very complex due to their fast packet processing. This review aims to study and compare different approaches to detecting DDoS attacks, using machine learning (ML) techniques such as k-means, K-Nearest Neighbors (KNN), and Naive Bayes (NB) used in intrusion detection systems (IDSs) and flow-based IDSs, and expresses data paths for packet filtering for HSN performance. This review highlights the high-speed network accuracy evaluation factors, provides a detailed DDoS attack taxonomy, and classifies detection techniques. Moreover, the existing literature is inspected through a qualitative analysis, with respect to the factors extracted from the presented taxonomy of irregular traffic pattern detection. Different research directions are suggested to support researchers in identifying and designing the optimal solution by highlighting the issues and challenges of DDoS attacks on high-speed networks.

---
### 2. Demystifying Performance of eBPF Network Applications (2025)
- **Authors**: Farbod Shahinfar, Sebastiano Miano, Aurojit Panda, Gianni Antichi
- **Citations**: 6 | **Relevance Score**: 23.0%
- **DOI**: https://doi.org/10.1145/3749216
- **Concepts**: Computer science
- **Extracted Techniques**: `eBPF` `ANN`

**Abstract:**
> Recently, eBPF has emerged as the latest answer to how we should accelerate networked applications. In this paper we ask can all networked applications benefit from eBPF? We answer this question by running several benchmarks under different workloads and by designing different test cases. Our results show that in reality many networked applications cannot benefit from eBPF, and worse the use of eBPF can limit how applications are deployed (because eBPF can lead to performance isolation violations) and the workloads they can handle. We then discuss whether ongoing work can fix the limitations we identify, and propose directions that the community might want to focus on.

---
### 3. Empowering Cloud Computing With Network Acceleration: A Survey (2024)
- **Authors**: Lorenzo Rosa, Luca Foschini, Antonio Corradi
- **Citations**: 41 | **Relevance Score**: 18.5%
- **DOI**: https://doi.org/10.1109/comst.2024.3377531
- **Concepts**: Cloud computing, Computer science, Acceleration, Computer security, Distributed computing
- **Extracted Techniques**: `DPDK` `RDMA` `XDP`

**Abstract:**
> Modern interactive and data-intensive applications must operate under demanding time constraints, prompting a shift toward the adoption of specialized software and hardware network acceleration technologies. This specialization, however, poses significant scalability, flexibility, security, and economic sustainability challenges for application developers. Cloud computing holds the potential to overcome these obstacles by offering the cost-effective option to access specialized acceleration technologies through standard cloud interfaces. Nevertheless, that integration is still challenging for cloud providers. In the cloud, physical resources are hidden behind a virtualization layer, whereas acceleration technologies make applications directly interact with the hardware. To bridge this gap, recent literature explores the possibility of empowering cloud platforms with accelerated networking as a commodity, thus offering the innovative option of Network Acceleration as a Service. This survey reviews these recent research efforts by adopting popular technologies like XDP, DPDK, and RDMA as a reference. To organize the surveyed research in a comprehensive framework, we identify four key aspects that pose critical problems to the integration of acceleration options in cloud computing -access interfaces, virtualization techniques, serviceability, and security -and systematically discuss the associated challenges. Then, we present the issues to be further addressed and outline the most promising research directions for the full integration of network acceleration within next-generation cloud computing platforms.

---