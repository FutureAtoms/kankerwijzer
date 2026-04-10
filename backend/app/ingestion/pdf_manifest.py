"""Explicit mapping from local PDF filenames to their public URLs and metadata."""

from __future__ import annotations

PDF_MANIFEST: dict[str, dict[str, str]] = {
    "rapport_UItgezaaide-kanker_2025_cijfers-inzichten-en-uitdagingen.pdf": {
        "canonical_url": "https://iknl.nl/uitgezaaide-kanker-2025",
        "source_id": "iknl-reports",
        "title": "Uitgezaaide kanker 2025: Cijfers, inzichten en uitdagingen",
        "publisher": "IKNL",
    },
    "rapport_manvrouwverschillenbij-kanker_definitief2.pdf": {
        "canonical_url": "https://iknl.nl/onderzoek/publicaties#man-vrouw-verschillen",
        "source_id": "iknl-reports",
        "title": "Man-vrouwverschillen bij kanker",
        "publisher": "IKNL",
    },
    "trendrapport_darmkanker_def.pdf": {
        "canonical_url": "https://iknl.nl/onderzoek/publicaties#trendrapport-darmkanker",
        "source_id": "iknl-reports",
        "title": "Trendrapport Darmkanker",
        "publisher": "IKNL",
    },
    "comorbidities_medication_use_and_overall_survival_in_eight_cancers.pdf": {
        "canonical_url": "https://iknl.nl/onderzoek/publicaties#comorbidities-medication",
        "source_id": "scientific-publications",
        "title": "Comorbidities, medication use, and overall survival in eight cancers",
        "publisher": "IKNL",
    },
    "head_and_neck_cancers_survival_in_europe_taiwan_and_japan.pdf": {
        "canonical_url": "https://iknl.nl/onderzoek/publicaties#head-neck-survival",
        "source_id": "scientific-publications",
        "title": "Head and neck cancers: survival in Europe, Taiwan and Japan",
        "publisher": "IKNL",
    },
    "ovarian_cancer_recurrence_prediction.pdf": {
        "canonical_url": "https://iknl.nl/onderzoek/publicaties#ovarian-recurrence",
        "source_id": "scientific-publications",
        "title": "Ovarian cancer recurrence prediction",
        "publisher": "IKNL",
    },
    "trends_and_variations_in_the_treatment_of_stage_I_III_non_small_cell_lung_cancer.pdf": {
        "canonical_url": "https://iknl.nl/onderzoek/publicaties#nsclc-treatment-trends",
        "source_id": "scientific-publications",
        "title": "Trends and variations in the treatment of stage I-III NSCLC",
        "publisher": "IKNL",
    },
    "trends_and_variations_in_the_treatment_of_stage_I_III_small_cell_lung_cancer.pdf": {
        "canonical_url": "https://iknl.nl/onderzoek/publicaties#sclc-treatment-trends",
        "source_id": "scientific-publications",
        "title": "Trends and variations in the treatment of stage I-III SCLC",
        "publisher": "IKNL",
    },
}
