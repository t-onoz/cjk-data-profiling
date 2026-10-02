# cjk-data-profiling

`cjk-data-profiling` is a context-manager package for generating
`ydata-profiling` / `fg-data-profiling` reports with Japanese, Chinese, or
Korean text. It temporarily configures CJK fonts for Matplotlib and WordCloud
and prevents report interaction DOM-ID collisions caused by column names.

## Installation

```bash
pip install cjk-data-profiling
```

Install the optional profiling dependency when needed:

```bash
pip install "cjk-data-profiling[profiling]"
```

## Usage

Wrap report generation in `cjk_data_profiling`.

```python
import pandas as pd
from data_profiling import ProfileReport

from cjk_data_profiling import cjk_data_profiling

dataframe = pd.DataFrame({"city": ["東京", "大阪"]})

with cjk_data_profiling("ja"):
    report = ProfileReport(dataframe)
    report.to_file("report.html")
```

Language-specific values are `"ja"`, `"zh-cn"`, `"zh-tw"`, and `"ko"`.
Use the additional `"mixed"` value only when a Noto Sans CJK font is
installed; it requires one font that covers Japanese, Chinese, and Korean text.

To prefer a different installed font, replace the candidate list for the
relevant language before entering the context. The selected font must include
the CJK characters used by the report.

```python
from cjk_data_profiling import FONT_CANDIDATES, cjk_data_profiling

FONT_CANDIDATES["ja"] = ["Yu Gothic", "Meiryo"]

with cjk_data_profiling("ja"):
    ...
```

All compatibility patches are enabled by default. To opt out of one, pass its
keyword-only switch. For example, leave WordCloud's default font unchanged:

```python
with cjk_data_profiling("ja", enable_wordcloud=False):
    report = ProfileReport(dataframe)
```

The available switches are `enable_matplotlib`, `enable_wordcloud`, and
`enable_slugify`.

The context temporarily changes process-wide Matplotlib and WordCloud defaults,
as well as the installed profiling package's report-structure DOM-ID helper.
*Concurrent report generation from multiple threads in the same process is not
supported.* Both this package and `fg-data-profiling` temporarily modify
Matplotlib global state while rendering. Do not make this context active in
overlapping threads, including with different languages. If reports must be
generated concurrently, use separate processes. For threaded applications,
serialize the complete report-generation operation with an application-level
lock instead.

## Testing

```bash
pytest
pytest -m integration
```

Run the non-integration suite on every supported Python version locally:

```bash
uv sync --group dev
uv run tox
```

`tox` obtains Python 3.11, 3.12, 3.13, and 3.14 through `uv`, then runs
`pytest -m "not integration"`. Report-generation integration tests remain
opt-in. The interaction-selector integration test writes
`*-interaction-selectors.html` files to `test_output/integration-reports/`.
Open one in a browser to manually confirm that every Interaction selector,
including `"a b"`, `"a-b"`, and CJK column names, displays its matching plot.

Integration reports and WordCloud images are written to
`test_output/integration-reports/` and are ignored by Git.
