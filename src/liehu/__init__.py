"""猎狐系统 (Fox Hunting System).

基于文章《我是怎么追踪银狐新域名的》的"壳/线/包"三层追踪方法论实现的
自动化威胁情报追踪系统。

三层模型:
    - 壳 (Shell)   : 不断变脸的前台页面 (域名/标题/品牌/模板)
    - 线 (Line)    : 控制接口 api.php / download_link / 分析ID / 下载路径
    - 包 (Package) : 载荷样本 MSI/PE, 完整哈希轮换但结构骨架持久

系统采用混合数据模式: 默认使用从文章 7·23 水位复原的模拟数据源,
配置 API Key 后可切换真实 URLScan / CertSpotter / RDAP / DoH。
"""

__version__ = "0.1.0"
