Real Exchange Rate Explorer
Python 3.12 Streamlit app for historical monthly bilateral real exchange rates, using IMF CPI and exchange-rate data. This app does not forecast future exchange rates.
Deploy without installing Python
1. Put app.py, requirements.txt, and this README.md at the top level of the public GitHub repository.
2. Sign in at https://share.streamlit.io using GitHub. Create an app, select the repository, main branch, and app.py.
3. Select Python 3.12 in Advanced settings. Leave Secrets empty. Deploy.
Data and economics
API: https://api.imf.org/external/sdmx/3.0
- CPI flow: IMF.STA/CPI; key {country}.CPI._T.IX.M.
- Exchange-rate flow: IMF.STA/ER; key {country}.XDC_USD.PA_RT.M.
- Euro area: G163. Countries are read from the IMF CPI country codelist.
- Latest flow version is requested using +. Complete individual series are fetched, then filtered locally from January 1976. IMF monthly dates such as 2024-M01 are parsed explicitly.
- USD per USD is exactly 1. Other exchange rates are IMF period-average local currency per USD.
- S = FX2_per_USD / FX1_per_USD: units of Country 2 currency per Country 1 currency.
- RER = S * CPI1 / CPI2.
- RER_star is the arithmetic mean of valid monthly RER observations in the selected sample, recalculated whenever dates change.
- Real_Index = 100 * RER / RER_star. Nominal S is never normalized.
Missing months stay blank, including in the downloadable CSV. Only complete, positive, finite RER observations enter the mean. No interpolation, forward filling, alternate data sources, or fabricated observations are used. A country appearing in metadata does not guarantee coverage. CPI scales are applied from IMF metadata; constant CPI rebasing cancels in the normalized real index. Currency reforms, euro adoption and methodological breaks require care when interpreting long samples. An index of 100 is the selected historical average, not an estimated equilibrium rate.
Using the app
Choose two countries, start/end months, and Real, Nominal, or Both. Both uses independent labeled axes. Download the selected sample CSV, including incomplete months, input CPIs/FX, S, RER, validity flag, RER_star and Real_Index. Requests have a timeout; errors appear on screen. Data are cached for six hours, country metadata for a day. Use Refresh IMF data to clear caches.
Assignment verification
1. Choose United Kingdom (GBR) as Country 1 and United States (USA) as Country 2. Confirm the label is USD per GBP.
2. Download CSV. For one valid row calculate 1 / FX1_per_USD, then multiply by CPI1 / CPI2. Compare with S and RER respectively.
3. Average the nonblank Real_Index column: it should be 100 within floating-point rounding. Change dates, download again, and repeat.
4. Test Real, Nominal, Both, a pair including G163, and a short/no-overlap sample.
5. Submit your deployed URL, repository URL, prompts/chat screenshots, model/date log, one manual verification, and the downloaded CSV.
Illustrative arithmetic only (not IMF observations): FX1=0.8, FX2=1, CPI1=120, CPI2=110 gives S=1.25 and RER=1.36363636. Use actual exported data for the submitted verification.
AI assistance log
Requested by Chris on October 26, 2026. Code generated with ChatGPT (GPT-6 Astra; interface/runtime label gpt-6-astra-wm). Preserve the conversation and record the model label shown in your interface for submission.
Troubleshooting
If IMF access fails, retry or use Refresh IMF data. If persistent, send the exact error and the three current files to the LLM. HTTP errors and unexpected metadata/CSV formats are shown rather than replaced with demo data. No API key is configured. Some network environments may block IMF access.
