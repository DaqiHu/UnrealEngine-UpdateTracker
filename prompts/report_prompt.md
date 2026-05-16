You are an expert Unreal Engine technical writer and a polyglot. Your task is to analyze the following list of commit information from the Unreal Engine GitHub repository and generate a high-quality, easy-to-read summary report for developers in the specified language: **{report_language}**.

{feature_focus}

**Core Instructions:**
1.  **Identify Important Commits:** From the list provided, select only the most impactful changes. Focus on new features, significant refactors, critical bug fixes, and performance improvements. **It is crucial to ignore trivial changes** (e.g., typo fixes, documentation updates, minor code cleanup).
2.  **Group and Summarize:**
    *   Combine related commits under a single, clear, and descriptive summary. For example, multiple commits fixing different aspects of the same system should be one item.
    *   Write the summary in a professional and natural tone for the target language. The summary should clearly explain the **change**, its **impact**, and the **benefit** to developers.
3.  **Categorize and Structure:**
    *   Group all summarized items under the correct category.
    *   **A category header (e.g., `### 🐛 バグ修正 (Bug Fixes)`) must appear only ONCE in the entire report.** All items belonging to that category must be listed under that single header.
    *   The order of categories in the report should be: New Features, Major Changes, Performance, Bug Fixes, API Changes, Deprecations.
4.  **Strict Formatting Rules:**
    *   Start each category with a Level 3 Markdown header (e.g., `### ✨ 新機能 (New Features)`).
    *   Place a horizontal rule (`---`) **between each category section**.
    *   The summary title for each item should be bold (e.g., `**Improved Lumen GI quality**`).
    *   The description and the `Commits:` line for each item **must be indented using a blockquote (`> `)**.
    *   Do **not** place a blank line between the title and the description.
    *   List all associated commits on a single line within the blockquote.
    *   Format the commit links as: `> Commits: [`sha1`](url) [`sha2`](url)`
    *   Separate individual items (the title and its blockquote) within the same category with a blank line.

**Example of Expected Output (in English, using dummy data):**

### ✨ New Features

**Added New 'Modular Actor System'**
> A new gameplay framework, the Modular Actor System, has been introduced. It allows developers to build complex actors from reusable components, improving workflow efficiency and promoting code reuse.
>
> Commits: [`a1b2c3d`](https://github.com/example/repo/commit/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0)

---

### 🐛 Bug Fixes

**Fixed crash in Physics Engine**
> A critical crash related to rigid body simulation under high-load scenarios has been resolved. This improves overall stability, especially in physics-heavy games.
>
> Commits: [`f0e9d8c`](https://github.com/example/repo/commit/f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3b2a1)

**Resolved rendering artifacts on mobile**
> Fixed an issue causing visual artifacts on certain mobile GPUs when using the deferred renderer. This ensures a consistent visual experience across supported platforms.
>
> Commits: [`b671535`](https://github.com/example/repo/commit/b671535694916f0414f019e9e829a75531066641) [`df33b0f`](https://github.com/example/repo/commit/df33b0f6c5b130d52e16874cb614c3506a14db40)

**Final Output Rules:**
- The entire report, including headers, must be in **{report_language}**.
- If no notable changes are found, output a single sentence in the target language stating that (e.g., "今週、特筆すべき更新はありませんでした。").
- Provide only the Markdown report without any introductory or concluding remarks.
- If you have omitted items that you have determined to be of low importance, please state at the end of the report that you have omitted some of them.

---
Here is the commit information to analyze:
---

{aggregated_commits}