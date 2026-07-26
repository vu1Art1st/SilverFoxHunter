"""数据处理分析模块。

包含四个核心分析器:
    - dedup       : UUID 去重 + page.domain 归一化
    - stablehash  : 去尾字节稳定区哈希
    - correlation : 多时钟分类 + 连接件归因聚类
    - diff        : 对比上一状态生成差异事件
"""
