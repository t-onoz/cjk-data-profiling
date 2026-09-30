# cjk-data-profiling

Temporary CJK font support for Matplotlib and WordCloud used by
`ydata-profiling` and `fg-data-profiling`.

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

The context temporarily changes process-wide Matplotlib and WordCloud defaults.
Concurrent use from multiple threads in the same process is not supported.

## Testing

```bash
pytest
pytest -m integration
```

Run the non-integration suite on every supported Python version locally:

```bash
tox
```

`tox` obtains Python 3.11, 3.12, 3.13, and 3.14 through `uv`, then runs
`pytest -m "not integration"`. Report-generation integration tests remain
opt-in.

Integration reports and WordCloud images are written to
`test_output/integration-reports/` and are ignored by Git.
