# Task 04 — Official medical-source connectors

Task 04 adds bounded, explicit connectors for three official public data services:

- **RxNav / RxNorm (NLM):** medication-name to RxCUI concept lookup.
- **openFDA drug labeling:** bounded search of submitted drug-label records.
- **DailyMed (NLM):** bounded search of Structured Product Label (SPL) records.

The endpoint shapes and query parameters follow the official API documentation:
RxNav APIs, openFDA drug-label API, and DailyMed REST API v2.

## Run a source fetch

Run commands from the repository root. Network access is required.

```powershell
# Resolve a medication name against RxNorm and stage the response
python -m scripts.fetch_medical_source rxnorm metformin

# Retrieve up to five openFDA label records
python -m scripts.fetch_medical_source openfda metformin --limit 5

# Search DailyMed SPL records
python -m scripts.fetch_medical_source dailymed metformin --page-size 10
```

For an isolated staging directory:

```powershell
python -m scripts.fetch_medical_source dailymed metformin `
  --staging-dir .\tmp\medical-evidence
```

## Safety and operational behavior

- Requests use fixed HTTPS endpoints; users cannot supply a URL or host.
- Redirects are disabled, requests have a finite timeout, and response size is bounded.
- Query values are sent as request parameters rather than interpolated into URL paths.
- Network and HTTP failures are raised as typed `ExternalAPIError` exceptions.
- Responses must be UTF-8 JSON objects and are passed to the Task 03 content-addressed evidence staging service.
- Each result remains `pending_clinical_review` and `staged_only`.
- Fetching evidence does not add aliases, alter runtime rule datasets, or create clinical recommendations.
- Source records represent API snapshots, not proof that every returned record applies to a particular formulation, patient, jurisdiction, or use.

## Provider-specific notes

- RxNav resolves terminology identifiers; an RxCUI match is not proof of clinical equivalence for every product, strength, or route.
- openFDA labeling is manufacturer-submitted labeling data and varies across products. openFDA explicitly warns against relying on its data for medical-care decisions.
- DailyMed returns SPL metadata/search results. A search result is not a complete review of the label; the SPL document and relevant sections still require human review.
- These services are US-focused. They do not establish availability, authorization, or labeling status in India or another jurisdiction.

## Official API references

- RxNav API overview: https://www.lhncbc.nlm.nih.gov/RxNav/APIs/index.html
- openFDA drug-label endpoint: https://open.fda.gov/apis/drug/label/
- openFDA authentication and rate limits: https://open.fda.gov/apis/authentication/
- DailyMed REST web services: https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm
- DailyMed v2 SPL search resource: https://dailymed.nlm.nih.gov/dailymed/webservices-help/v2/spls_api.cfm

Passing software tests validates connector behavior under test conditions. It does not validate clinical accuracy, completeness, currency, or suitability of fetched records.


## NLM attribution

For applications using NLM data, include the NLM-requested attribution: “This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes of Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse or recommend this or any other product.”
