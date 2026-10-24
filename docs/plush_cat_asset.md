# TOMC 四阶段猫头素材与历史参考

- 工具：内置 `image_gen.imagegen`，非 CLI。
- 当前项目文件：`src/tomc/data/tomc-expression-1.png` 至 `src/tomc/data/tomc-expression-4.png`，分别对应第 1 至第 4 阶段。所有阶段的名称始终为 TOMC，包括多计数器状态；进化只改变外观，不再使用分阶段名称。
- 四个文件均为双帧 RGBA PNG：左帧待机没精打采、委屈放空，右帧处理上下文时开心。本轮仅编辑左帧，使眉毛内高外低呈柔软八字形、眼神松弛无焦点，避免凶相；工作笑脸沿用。保留生成的透明 alpha；Qt 按动画状态选取相应半幅并在绘制时缩放，不额外绘制嘴巴。
- 四阶段均只有猫头，眼睛比此前参考稍大。最新前三阶依次为浅色稀疏细绒、适中短绒、浓密厚绒与饱满脸颊，均没有黄色额顶毛簇和金色菱形额纹；第四阶保留黄毛、皇冠和直接连接头两侧的翅膀。没有身体、脖子、四肢或口袋。此前全身候选没有被选用。
- 最新四阶段待机表情提示词完整保存在 [tomc_dejected_expression_prompt.md](tomc_dejected_expression_prompt.md)。前三阶材质编辑历史见 [tomc_material_prompts.md](tomc_material_prompts.md)，原双帧表情过程见 [tomc_expression_prompts.md](tomc_expression_prompts.md)；这些历史中的 grumpy 方向已被最新委屈放空表情覆盖。仅上下文处理动画进行时使用右帧，包括第二阶三次顶撞整理，结束恢复左帧；待机点击统计不触发笑脸。运行时凝实度仍按 35% / 58% / 82% / 100% 连续插值。本轮源码、独立预览与候选包使用当前四个双帧素材，全局已安装插件未更新。
- 素材为原创生成候选，不含品牌标识；不把风格参考表述为品牌授权或法律保证。

## 历史参考猫头

最新委屈表情编辑前的四张双帧素材备份在 `outputs/dejected_cat_20261018/previous_assets`；更早的材质更新前版本备份在 `outputs/forge_head_20261018/previous_assets`。旧提示词按原文保留；其中前三阶的毛簇、金色额纹及 grumpy 表情描述不再代表当前素材。

此前四张 `src/tomc/data/tomc-head-1.png` 至 `src/tomc/data/tomc-head-4.png` 为 1254 × 1254 RGBA PNG，现保留为各阶段身份与装饰的编辑参考，不是当前运行时素材，也不打入当前候选包。其原始编辑提示词保存在 [tomc_evolution_prompts.md](tomc_evolution_prompts.md)。

此前认可的 `src/tomc/data/plush-cat-head.png` 仍保留为四阶段编辑参考和历史素材，不是当前运行时猫头。原始输出为 `%USERPROFILE%/.codex/generated_images/01a1502c-26fc-73d0-b090-71e60b519dba/exec-b4ee4923-b316-484e-ac86-7ddf6f15dec6.png`，尺寸 1254 × 1254。

以下提示词原样保存，仅记录此前无配件单猫头的生成过程；其中的小眼睛、无皇冠和无翅膀要求已由后续四阶段方向覆盖。

## 历史原始生成提示词

```text
ONE original desktop mascot asset: ONLY A PLUSH CAT HEAD. No body, no neck, no paws, no pocket, no accessories, no wings, no crown, no cape, no notes, no text. Transparent background. This must be unmistakably a CAT, never a dog or teddy bear. Soft wide flattened cat head, TWO UPRIGHT triangular feline ears with small peach inner triangles, no floppy ears. Broad cheeks, short flat cat muzzle integrated into face (no projecting muzzle), tiny upside-down pink triangle nose, very tiny stitched cat mouth, three short fine whiskers on each cheek. Tiny wide-set black glass bead eyes with slightly asymmetric height, vacant lovable awkward-cute silly expression. Extremely cute plush collectible photography, original design in premium whimsical plush aesthetic, not a replica of any brand's existing character, no logos. Soft short oatmeal beige plush with faint ruddy cinnamon on ears, ivory muzzle area; gently fuzzy, tactile handcrafted stitching, NOT cartoon/anime/vector illustration. Design novelty lies in stupidly tiny bead eyes on enormous squished cheeks and a slightly crooked cat mouth. Front facing, head upright and symmetrical silhouette, head fills 85% of square canvas, generous transparent edge. TWO pointy ears and whiskers are mandatory CAT anatomy. Soft neutral studio light, genuine transparent alpha outside fluffy silhouette. Single head centered, do not draw any detached extras. No background shadow. This is meant for a 140px desktop pet and needs very clear feline silhouette.
```
