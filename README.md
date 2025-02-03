# WaveAssist Helper Library
WaveAssist Helper Library

## Installation

```bash
pip install waveassist
```

## Usage

```python
from waveassist import WAHelper
wa_helper = WAHelper(uid='your_uid_token')

df = ... # your dataframe
wa_helper.set_dataframe('your_df_name', df)

df = wa_helper.get_dataframe('your_df_name')
print(df)

```