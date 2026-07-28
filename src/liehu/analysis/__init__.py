"""数据处理分析模块。

包含五个核心分析器:
    - dedup       : UUID 去重 + page.domain 归一化
    - stablehash  : 去尾字节稳定区哈希
    - correlation : 多时钟分类 + 连接件归因聚类 (含控制域接管/下载池)
    - diff        : 对比上一状态生成差异事件
    - ioc_priority: IOC 优先级分级 (P1/P2/P3) 与处置类别 (block/仅聚类)
"""
