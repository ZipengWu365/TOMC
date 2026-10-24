"""A conditional environmental story, not a resource-meter conversion."""

STORY = """<h3>少一点重复，让资源更多留给自然</h3>
<p>TOMC 把任务需要的信息整理得更紧凑，减少可能反复发送给模型的输入文本。</p>
<p><b>少发 token → 有机会少做计算。</b><br>
只有整理后的内容真的被发送，而且没有额外重试或其他开销抵消收益，才可能降低实际计算需求。
目前小猫记录的是文本量估算，还没有测量服务器的实际计算量。</p>
<p><b>少做计算 → 有机会少用电。</b><br>
模型运行在服务器上，需要电力；但耗电还取决于模型、硬件、批处理、缓存和利用率，
不能把 token 的减少比例直接当作省电比例。</p>
<p><b>少用电、少发热 → 有机会减少用水压力。</b><br>
部分数据中心用水散热，发电也可能消耗水。地点、时段、能源和冷却方式都会影响结果，
因此这里不把 token 换算成升水，也不宣称已经测得节水成果。</p>
<p><b>沙漠变绿洲，是这份心愿的画面。</b><br>
水留下来，树木、花草和动物回到画面里：它象征减少不必要的资源消耗、把资源留给自然。
皇冠是你的虚拟成长纪念，不代表现实中已经造林或修复沙漠。</p>
<p>研究依据：<a href="https://arxiv.org/abs/2304.03271">Making AI Less “Thirsty”</a>。
费用与环境是两套口径：官方单价可以用于估算输入价值，水和电仍未实测。</p>"""

CAPTIONS = (
    ("先少一点重复", "减少多余输入，有机会少做计算"),
    ("让计算轻一点", "若计算量真正下降，就可能减少用电"),
    ("让资源留给自然", "用电与冷却需求降低，有机会减轻用水压力"),
    ("把这份心愿，种成绿洲", "虚拟成长纪念 · 未测量实际节水量"),
)

STORY_EN = """<h3>Less repetition, more resources left for nature</h3>
<p>TOMC organizes task-relevant information into a more compact context, reducing input text that may otherwise be sent to a model repeatedly.</p>
<p><b>Fewer input tokens may mean less computation.</b><br>
Actual compute demand can fall only if the prepared context is sent and extra retries or other overhead do not cancel the benefit.
The cat records estimates of text size; it has not measured server computation.</p>
<p><b>Less computation may mean less electricity.</b><br>
Models run on servers that consume power. Energy use also depends on the model, hardware, batching, caching and utilization.
A token reduction percentage cannot be treated as an electricity saving percentage.</p>
<p><b>Lower electricity and cooling demand may ease water pressure.</b><br>
Some data centers use water for cooling, and power generation can also consume water. Results depend on location, time, energy sources and cooling methods.
This story does not convert tokens into liters or claim measured water savings.</p>
<p><b>A desert becoming an oasis illustrates that hope.</b><br>
Water, trees, flowers and animals return to the scene as a symbol of reducing unnecessary resource use and leaving resources for nature.
The crown marks virtual growth; it does not mean that trees have been planted or a desert restored.</p>
<p>Research reference: <a href="https://arxiv.org/abs/2304.03271">Making AI Less “Thirsty”</a>.
Cost and environmental impact use different measures. Official prices can support reference input-value estimates; water and electricity remain unmeasured.</p>"""

CAPTIONS_EN = (
    ("Start with less repetition", "Fewer unnecessary inputs may mean less computation"),
    ("Make computation lighter", "If compute demand falls, electricity use may fall too"),
    ("Leave resources for nature", "Lower power and cooling demand may ease water pressure"),
    ("Turn that wish into an oasis", "A virtual milestone · Actual water savings are unmeasured"),
)


def story_html(language=None):
    return STORY_EN if getattr(language, "code", language) == "en" else STORY


def captions(language=None):
    return CAPTIONS_EN if getattr(language, "code", language) == "en" else CAPTIONS
