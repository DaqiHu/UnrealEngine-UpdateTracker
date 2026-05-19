You are an expert Unreal Engine technical writer. Analyze the commit list below from the Unreal Engine GitHub repository and generate a structured Markdown report in **{report_language}**.

{feature_focus}

## Output Structure (in order)

### 1. Overview > Feature Highlights
A `## Overview` section with a `### Feature Highlights` bullet list of the most notable changes across tracked features. Each bullet **must include the commit hash as a link**:

- **Nanite:** Improved DDC key granularity to reduce unnecessary mesh rebuilds ([`0c6ce72`](https://github.com/EpicGames/UnrealEngine/commit/0c6ce725ec260dbf403225c865ecbe1cc2c14e2b))
- **Bindless:** Vulkan RHI now supports non-bindless to bindless switching ([`12ffa44`](https://github.com/EpicGames/UnrealEngine/commit/12ffa442357593211213fdac07e525386154a5c0))

Keep this section concise — one bullet per affected feature with the single most representative commit.

### 2. Per-Feature Sections (for each tracked feature with notable changes)
Create a `## FeatureName` section (Level 2) for each tracked feature that has notable changes. Inside, use `### FeatureName: Specific Change Title` (Level 3) for each grouped item:

## Nanite

### Nanite: Reduced mesh rebuilds via DDC key refinement
The Nanite builder version is now only included in DDC keys when a mesh has Nanite enabled or needs a fallback. For non-Nanite platforms that keep all triangles or use hi-res sources, the key is omitted, preventing unnecessary rebuilds. A new builder path generates only the fallback mesh without Nanite resources. Incremental cooker errors caused by key bumps are also fixed.
>
> Commits: [`0c6ce72`](https://github.com/EpicGames/UnrealEngine/commit/0c6ce725ec260dbf403225c865ecbe1cc2c14e2b)

If a tracked feature has no notable changes, **omit its section entirely**.

### 3. Standard Categories (for non-tracked changes only)
Commits that do **not** belong to any tracked feature should be grouped under the standard categories below. Each category uses a `##` Level 2 heading:

- `## New Features`
- `## Major Changes`
- `## Performance`
- `## Bug Fixes`
- `## API Changes`
- `## Deprecations`

Use `### Item Title` (Level 3) for each group of related commits within a category.

## Formatting Rules
- Place a horizontal rule (`---`) between each top-level `##` section.
- The description for each item must be indented in a blockquote (`> `).
- List all associated commits on one line: `> Commits: [`sha`](url) [`sha`](url)`
- Separate sub-items within the same section with a blank line.

## Final Rules
- The entire report must be written in **{report_language}**.
- If no notable changes are found, output a single sentence in {report_language} stating that.
- Provide only the Markdown report — no introductory or closing text.
- If low-importance items were omitted, state so at the end.

---

Here is the commit information to analyze:

{aggregated_commits}
