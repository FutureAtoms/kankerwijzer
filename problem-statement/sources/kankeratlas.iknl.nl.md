# Cancer Atlas

## What is this source?
The **Cancer Atlas** (https://kankeratlas.iknl.nl/) is an interactive geographical tool developed by IKNL. It visualises cancer incidence across the Netherlands compared to the Dutch average using data from the **Netherlands Cancer Registry (NCR)**.

The [Cancer Atlas](https://kankeratlas.iknl.nl/) enables users to explore **regional differences and trends** in cancer burden, supporting:

- Epidemiological research  
- Healthcare planning and capacity analysis  
- Policy development and evaluation  
- Public health communication  

The atlas typically presents data by geographic unit (pc3 - referring to the first three digits of the Dutch postal code (*3‑cijferige postcodegebied*)), cancer type, and sex.

## How to access the data (for this hackathon)?

The [Cancer Atlas](https://kankeratlas.iknl.nl/) is primarily designed as a **visual, interactive web application**, but its underlying data is exposed through web services that are used by the atlas front‑end itself.

### Get all filters

```python
import requests
from pprint import pprint

data_filters = requests.get("https://kankeratlas.iknl.nl/locales/nl/filters.json?format=json").json()
pprint(data_filters)
```

### Get cancer group info
```python
data_cancergrp = requests.get("https://iknl-atlas-strapi-prod.azurewebsites.net/api/cancer-groups/cancergrppc", params={"locale": "nl"}).json()
pprint(data_cancergrp)
```

### Get postcode info
```python
data_pc3 = requests.get("https://iknl-atlas-strapi-prod.azurewebsites.net/api/postcodes/getbypc/3").json()
pprint(data_pc3)
```

### Get data for specific cancer group, sex and postcode
```python
cancergrp = 11
sex = 3
postcode = 3

url = "https://iknl-atlas-strapi-prod.azurewebsites.net/api/cancer-datas/getbygroupsexpostcode/"

data_cancer = requests.get(f"{url}{cancergrp}/{sex}/{postcode}").json()
pprint(data_cancer)
```
This last request returns data per postcode for the given cancer group and sex. The data as seen on the map on the website can be taken from the item "p50".

For example, for people (sex=3) with lung cancer (cancergrp=11) and postcode 103, the value p50=1.46, which means the incidence rate is 46% above the expectation based on the Dutch average.
You'll see this 46% back if you hover over the area with postcode 103 (Amsterdam North) on the map for lung cancer.
<br><br>


> **Hackathon note**  
> Access methods are intentionally left open. The goal is not to reverse‑engineer the atlas, but to explore how this type of data could be used to create new insights, interfaces, or decision‑support tools.
