"""Monthly bilateral real exchange rates from IMF SDMX 3.0."""
from io import StringIO
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE = 'https://api.imf.org/external/sdmx/3.0'


def download(path, accept):
    req = Request(BASE + path, headers={'Accept': accept, 'User-Agent': 'RealExchangeRateStudentApp/1.0'})
    try:
        with urlopen(req, timeout=60) as response:
            return response.read().decode('utf-8-sig')
    except HTTPError as exc:
        if exc.code in (404, 204):
            return ''
        raise RuntimeError(f'IMF HTTP {exc.code}: {path}. Try again later.') from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError('IMF download timed out or could not connect. Try again later.') from exc


@st.cache_data(ttl=86400, show_spinner=False)
def countries():
    xml = download('/structure/dataflow/IMF.STA/CPI/+?references=all',
                   'application/vnd.sdmx.structure+xml;version=3.0.0')
    root = ET.fromstring(xml)
    result = {}
    for cl in root.iter():
        if cl.tag.split('}')[-1] != 'Codelist' or 'COUNTRY' not in cl.get('id', '').upper():
            continue
        for code in cl:
            ident = code.get('id', '')
            if not ((len(ident) == 3 and ident.isalpha()) or ident == 'G163'):
                continue
            names = [n for n in code if n.tag.split('}')[-1] == 'Name']
            english = next((n.text for n in names if n.get('{http://www.w3.org/XML/1998/namespace}lang') == 'en'), None)
            result[ident] = english or (names[0].text if names else ident)
    result['G163'] = 'Euro area'
    if 'GBR' not in result or 'USA' not in result:
        raise RuntimeError('Could not read the IMF country list. Please retry; the metadata format may have changed.')
    return result


def parse_series(text, code):
    if not text.strip():
        return pd.Series(dtype=float)
    frame = pd.read_csv(StringIO(text))
    if not {'TIME_PERIOD', 'OBS_VALUE'}.issubset(frame):
        raise ValueError('IMF response is not the expected observation CSV.')
    if 'COUNTRY' in frame:
        frame = frame[frame.COUNTRY == code].copy()
    dates = frame.TIME_PERIOD.astype(str).str.replace(r'^(\d{4})-M(\d{2})$', r'\1-\2', regex=True)
    frame['month'] = pd.to_datetime(dates, format='%Y-%m', errors='coerce')
    frame['value'] = pd.to_numeric(frame.OBS_VALUE, errors='coerce')
    if 'SCALE' in frame:
        frame['value'] *= 10.0 ** pd.to_numeric(frame.SCALE, errors='coerce').fillna(0)
    frame = frame.dropna(subset=['month'])
    if frame.month.duplicated().any():
        raise ValueError('IMF returned multiple observations for one month; refusing to choose arbitrarily.')
    s = frame.set_index('month').value.sort_index()
    return s.loc[s.index >= '1976-01-01'].where(lambda x: (x > 0) & (x < float('inf')))


@st.cache_data(ttl=21600, show_spinner=False)
def series(code, kind):
    flow, key = ('CPI', f'{code}.CPI._T.IX.M') if kind == 'cpi' else ('ER', f'{code}.XDC_USD.PA_RT.M')
    # Fetch the complete series and filter locally: avoids silently ignored time parameters.
    return parse_series(download(f'/data/dataflow/IMF.STA/{flow}/+/{key}', 'text/csv'), code)


def calculate(inputs):
    out = inputs.copy()
    out['S_C2_per_C1'] = out.FX2_per_USD / out.FX1_per_USD
    out['RER'] = out.S_C2_per_C1 * out.CPI1 / out.CPI2
    out['valid_RER'] = out.RER.notna() & (out.RER > 0) & (out.RER < float('inf'))
    out['RER'] = out.RER.where(out.valid_RER)
    out['RER_star'] = out.RER.mean()
    out['Real_Index'] = 100 * out.RER / out.RER_star
    return out


def main():
    st.set_page_config(page_title='Real Exchange Rate Explorer', layout='wide')
    st.title('Real Exchange Rate Explorer')
    st.caption('Monthly IMF data • Historical bilateral exchange rates • January 1976 onward where available')
    if st.sidebar.button('Refresh IMF data'):
        st.cache_data.clear()
    try:
        with st.spinner('Loading IMF countries…'):
            names = countries()
    except Exception as exc:
        st.error(str(exc)); st.stop()
    options = sorted(names, key=lambda c: names[c])
    c1 = st.sidebar.selectbox('Country 1', options, index=options.index('GBR'), format_func=lambda c: f'{names[c]} ({c})')
    c2 = st.sidebar.selectbox('Country 2', options, index=options.index('USA'), format_func=lambda c: f'{names[c]} ({c})')
    mode = st.sidebar.radio('Chart', ['Real', 'Nominal', 'Both'], index=2)
    st.write(f'**S = units of {names[c2]} currency per one unit of {names[c1]} currency.**')
    if (c1, c2) == ('GBR', 'USA'):
        st.info('UK → US: the nominal exchange rate is USD per GBP.')
    try:
        with st.spinner('Downloading monthly IMF CPI and exchange rates…'):
            data = {}
            for n, code in enumerate((c1, c2), 1):
                data[f'CPI{n}'] = series(code, 'cpi')
                if code != 'USA':
                    data[f'FX{n}_per_USD'] = series(code, 'fx')
            raw = pd.DataFrame(data)
            if raw.empty:
                st.warning('No monthly observations available for this pair.'); st.stop()
            for n, code in enumerate((c1, c2), 1):
                if code == 'USA':
                    raw[f'FX{n}_per_USD'] = 1.0  # USD per USD is an identity.
    except Exception as exc:
        st.error(f'Data could not be loaded: {exc}'); st.stop()
    last = min(raw.index.max(), pd.Timestamp.today().to_period('M').to_timestamp())
    months = pd.date_range('1976-01-01', last, freq='MS')
    labels = months.strftime('%Y-%m').tolist()
    a, b = st.columns(2)
    start = a.selectbox('Start month', labels, index=0)
    end = b.selectbox('End month', labels, index=len(labels)-1)
    if start > end:
        st.error('Start month must be on or before end month.'); st.stop()
    sample = raw.reindex(pd.date_range(start, end, freq='MS'))
    for n, code in enumerate((c1, c2), 1):
        if code == 'USA': sample[f'FX{n}_per_USD'] = 1.0
    out = calculate(sample)
    count = int(out.valid_RER.sum())
    st.caption(f'{count} valid real observations out of {len(out)} selected months. Missing values are not filled or interpolated.')
    if not count:
        st.warning('No complete CPI/FX overlap in this sample. Try different dates or countries. Nominal data may still be available.')
    elif count < len(out):
        st.warning('Some selected months lack inputs. The real average uses only complete months; gaps remain visible.')
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    if mode in ('Real', 'Both'):
        fig.add_trace(go.Scatter(x=out.index, y=out.Real_Index, name='Real index', connectgaps=False), secondary_y=False)
        fig.add_hline(y=100, line_dash='dot', secondary_y=False)
    if mode in ('Nominal', 'Both'):
        fig.add_trace(go.Scatter(x=out.index, y=out.S_C2_per_C1, name='Nominal S', connectgaps=False), secondary_y=(mode == 'Both'))
    fig.update_yaxes(title_text='Nominal S (C2 currency / C1 currency)' if mode == 'Nominal' else 'Real index (sample average = 100)', secondary_y=False)
    if mode == 'Both': fig.update_yaxes(title_text='Nominal S (C2 currency / C1 currency)', secondary_y=True)
    fig.update_layout(hovermode='x unified', height=500, legend=dict(orientation='h'))
    st.plotly_chart(fig, use_container_width=True)
    st.caption('A higher real index means real appreciation of Country 1 relative to Country 2 compared with the selected-sample average. 100 is a sample benchmark, not proof of fair value.')
    export = out.copy()
    export.insert(0, 'Country2', c2); export.insert(0, 'Country1', c1)
    export.index = export.index.strftime('%Y-%m'); export.index.name = 'Month'
    st.download_button('Download selected sample CSV', export.to_csv().encode('utf-8'), f'RER_{c1}_{c2}_{start}_{end}.csv', 'text/csv')
    with st.expander('Observations and calculations'):
        st.dataframe(export)
    with st.expander('How the calculations work'):
        st.markdown('**S = FX2 / FX1** (both FX inputs are local currency per USD).\n\n**RER = S × CPI1 / CPI2**\n\n**RER* = mean of valid RER values within the selected dates**\n\n**Real index = 100 × RER / RER***\n\nCPI values are indices, not literal basket prices. Constant rebasing cancels in the real index. Currency reforms, euro adoption, and methodological breaks can affect long historical comparisons. No missing observations are invented. USD per USD is fixed at 1 by definition.')
        st.markdown('[IMF data API](https://data.imf.org/en/Resource-Pages/IMF-API)')


if __name__ == '__main__':
    main()
