import streamlit as st
import pandas as pd

st.set_page_config(page_title="YC S25 Companies Directory", layout="wide")

st.title("Y Combinator S25 Companies Directory")

@st.cache_data
def load_data():
    return pd.read_csv("yc_s25_companies.csv")

df = load_data()

st.markdown("""
**Columns:**
- YC company name
- Website
- Description
- Link to YC page
- Link to LinkedIn page
- Flag for whether 'YC S25' is mentioned on LinkedIn
""")

def make_clickable(url, text=None):
    if pd.isna(url):
        return ""
    if not text:
        text = url
    return f'<a href="{url}" target="_blank">{text}</a>'

# Prepare display DataFrame
show_df = df.copy()
show_df['YC Page'] = show_df['yc_link'].apply(lambda x: make_clickable(x, 'YC Profile'))
show_df['LinkedIn'] = show_df['linkedin_url'].apply(lambda x: make_clickable(x, 'LinkedIn'))
show_df['Website'] = show_df['website'].apply(lambda x: make_clickable(x, 'Website'))
show_df['YC S25 on LinkedIn'] = show_df['yc_s25_on_linkedin'].apply(lambda x: '✅' if x else '❌')

show_df = show_df.rename(columns={
    'name': 'Name',
    'description': 'Description',
})

st.write(f"Total companies: {len(show_df)}")

st.write(
    show_df[[
        'Name', 'Website', 'Description', 'YC Page', 'LinkedIn', 'YC S25 on LinkedIn'
    ]].to_html(escape=False, index=False), unsafe_allow_html=True
) 