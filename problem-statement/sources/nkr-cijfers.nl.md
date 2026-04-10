# NKR Cijfers

## What is this source?
IKNL (Integraal Kankercentrum Nederland) manages and maintains the Netherlands Cancer Registry (NCR); a population-based database about cancer in NL. IKNL is responsible for collecting, validating, analysing and disseminating this database.<br> The website https://nkr-cijfers.iknl.nl is one of the primary ways in which these data are made available to a broad audience. It presents the main national cancer statistics in an accessible and structured way.

The website provides:
- Official national cancer statistics derived from the Netherlands Cancer Registry
- Data on incidence, prevalence, survival, stage, and trends over time
- Interactive tables and charts that allow users to explore data by tumour type, year, age, sex, and region
- Aggregated, anonymised data suitable for public use, research, and policy support

In short, [NKR Cijfers](https://nkr-cijfers.iknl.nl) offers direct insight into the core statistics of the Netherlands Cancer Registry, curated and published by IKNL for public access.

## How to use the API of NKR Cijfers?
In addition to the interactive website, NKR Cijfers offers a public API that provides programmatic access to the same aggregated statistics displayed on [NKR Cijfers](https://nkr-cijfers.iknl.nl).


General usage pattern:

Select a topic (for example incidence, survival, or stage distribution)
Retrieve the available filters and configuration for that topic
Build a query by specifying filters (such as cancer type, year, age group, or region)
Submit the query to retrieve aggregated cancer statistics as JSON



### Get all navigation items

```python
import requests
from pprint import pprint

body = {"language": "nl-NL"}
data = requests.post("https://api.nkr-cijfers.iknl.nl/api/navigation-items?format=json", json=body).json()
pprint(data)
```

### Get configuration for a specific navigation item 
(for example: incidentie/verdeling-per-stadium)

```python
body = {"language":"nl-NL",
        "currentNavigation":{"code":"incidentie/verdeling-per-stadium"}
        }
data = requests.post("https://api.nkr-cijfers.iknl.nl/api/configuration?format=json", json=body).json()
pprint(data)
```

### Get all filter groups for a specific navigation item 
(for example: incidentie/verdeling-per-stadium)

```python
body = {"currentNavigation":
            {"code":"incidentie/verdeling-per-stadium"},
        "language":"nl-NL",
        "filterValuesSelected": [],
        "userAction":{"code":"restart","value":""}
        }
data = requests.post("https://api.nkr-cijfers.iknl.nl/api/filter-groups?format=json", json=body).json()
pprint(data)
```

### Example query for a specific navigation item with specific filters and aggregated by values
(for example: incidentie/verdeling-per-stadium) 

```python
body = {
    "language": "nl-NL",
    "navigation": {"code": "incidentie/verdeling-per-stadium"},
    "groupBy": [
        {
            "code": "filter/stadium",
            "values": [
                {"code": "stadium/0"},
                {"code": "stadium/i"},
                {"code": "stadium/ii"},
                {"code": "stadium/iii"},
                {"code": "stadium/iv"},
                {"code": "stadium/x"},
                {"code": "stadium/nvt"}
            ]
        }
    ],
    "aggregateBy": [
        {
            "code": "filter/kankersoort",
            "values": [{"code": "kankersoort/totaal/alle"}]
        },
        {
            "code": "filter/periode-van-diagnose",
            "values": [{"code": "periode/1-jaar/2024"}]
        },
        {
            "code": "filter/geslacht",
            "values": [{"code": "geslacht/totaal/alle"}]
        },
        {
            "code": "filter/leeftijdsgroep",
            "values": [{"code": "leeftijdsgroep/totaal/alle"}]
        },
        {
            "code": "filter/regio",
            "values": [{"code": "regio/totaal/alle"}]
        }
    ],
    "statistic": {"code": "statistiek/verdeling"}
}

data = requests.post("https://api.nkr-cijfers.iknl.nl/api/data?format=json", json=body).json()
pprint(data)
```

This last query gives you the data of the distribution of incidence per stadium for all cancer types, for the last year. Similar to https://nkr-cijfers.iknl.nl/viewer/incidentie-verdeling-per-stadium.

Play around with the navigation items and filters for different views.