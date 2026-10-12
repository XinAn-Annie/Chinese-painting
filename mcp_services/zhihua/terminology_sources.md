# 中国画受控术语词表来源与边界

## 当前范围

`terminology_glossary.json` 当前包含 33 项术语。第一版 17 项来自 `ZhiHua_QA` 高频技法词并经人工收敛；第二版依据博物馆公开资料新增 16 项：

- 皴法：解索皴、牛毛皴、雨点皴、卷云皴
- 笔墨和花鸟：点苔、渲染、勾花点叶、兼工带写、勾勒
- 构图空间：平远、高远、深远、散点透视、留白
- 建筑与设色：界画、小青绿

## 主要资料来源

- 故宫博物院“皴”词条：<https://www.dpm.org.cn/lemmas/242610.html>
- 故宫博物院“斧劈皴”词条：<https://www.dpm.org.cn/lemmas/243376.html>
- 故宫博物院《窠石平远图》：<https://www.dpm.org.cn/collection/paint/228299.html>
- 故宫博物院“界画”词条：<https://www.dpm.org.cn/lemmas/240644.html>
- 故宫博物院“兼工带写”词条：<https://www.dpm.org.cn/lemmas/240400.html>
- 故宫博物院“勾花点叶”词条：<https://www.dpm.org.cn/lemmas/239344.html>
- 故宫博物院《沧洲趣图》：<https://www.dpm.org.cn/collection/paint/234540.html>
- 故宫博物院《夏山高隐图》：<https://www.dpm.org.cn/collection/paint/228384.html>
- 故宫博物院《秋山萧寺图》：<https://www.dpm.org.cn/collection/paint/257004.html>
- 故宫博物院《昌黎诗意图》：<https://www.dpm.org.cn/collection/paint/231775.html>
- 大都会艺术博物馆“Mastering the Art of Chinese Painting”：<https://www.metmuseum.org/exhibitions/listings/2010/xie-zhiliu>
- 香港中文大学文物馆“山水有皴法”：<https://www.artmuseum.cuhk.edu.hk/en/exhibition/current/detail/66>

## 纳入原则

1. 术语必须能对应画面中可描述的线条、墨色、颜色、空间或物象关系。
2. 每项规则通常要求两至三类证据同时出现；单独出现“山”“颜色”“线条”等词不触发。
3. 涉及工具或材料的判断采用“倾向”，例如仅凭数字图片不能确认界尺或矿物颜料。
4. 不纳入作者、流派、年代、作品名称、寓意、人格评价、真伪与价格判断。
5. 不把题材名当成技法，也不把博物馆对某件作品的结论直接套用到用户图片。

## 使用限制

词表只规范模型已经描述出的可见证据，不能证明真实创作步骤，也不能完全消除视觉模型对物象的识别错误。新增或修改规则后应运行 `python -m unittest -v test_terminology.py`，并使用含目标特征和不含目标特征的图片分别测试。
