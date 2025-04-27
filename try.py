import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests
from bs4 import BeautifulSoup
import re
import time


st.set_page_config(
    page_title="Books Analysis Dashboard",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)



st.title("📚 Books to Scrape Analysis Dashboard")
st.markdown("""
This interactive dashboard analyzes book data scraped from [books.toscrape.com](http://books.toscrape.com/).
Explore pricing, ratings, availability, and more!
""")


st.sidebar.header("Controls")
pages_to_scrape = st.sidebar.slider("Number of pages to scrape", 1, 5, 2)
scrape_button = st.sidebar.button("Scrape Fresh Data")


@st.cache_data(show_spinner="Scraping book data...")
def scrape_books(pages_to_scrape):
    base_url = "http://books.toscrape.com/"
    all_books = []
    
    for page in range(1, pages_to_scrape + 1): 
        with st.spinner(f"Scraping page {page}..."):
            url = f"{base_url}catalogue/page-{page}.html"
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            books = soup.find_all('article', class_='product_pod')
            
            for book in books:
                title = book.h3.a['title']
                price = book.find('p', class_='price_color').text
                rating = book.p['class'][1]
                
                availability_text = book.find('p', class_='instock availability').text.strip()
                availability_match = re.search(r'\((\d+) available\)', availability_text)
                availability = int(availability_match.group(1)) if availability_match else (1 if 'In stock' in availability_text else 0)
                
                book_url = base_url + 'catalogue/' + book.h3.a['href']
                book_response = requests.get(book_url)
                book_soup = BeautifulSoup(book_response.text, 'html.parser')
                
                description = book_soup.find('meta', attrs={'name': 'description'})['content'].strip()
                
                upc = book_soup.find('th', string='UPC').find_next_sibling('td').text
                product_type = book_soup.find('th', string='Product Type').find_next_sibling('td').text
                price_excl_tax = book_soup.find('th', string='Price (excl. tax)').find_next_sibling('td').text
                price_incl_tax = book_soup.find('th', string='Price (incl. tax)').find_next_sibling('td').text
                tax = book_soup.find('th', string='Tax').find_next_sibling('td').text
                num_reviews = book_soup.find('th', string='Number of reviews').find_next_sibling('td').text
                
                all_books.append({
                    'title': title,
                    'price': price,
                    'rating': rating,
                    'availability': availability,
                    'upc': upc,
                    'product_type': product_type,
                    'price_excl_tax': price_excl_tax,
                    'price_incl_tax': price_incl_tax,
                    'tax': tax,
                    'num_reviews': num_reviews,
                    'description': description
                })
                
                time.sleep(0.5)
    
    return pd.DataFrame(all_books)

@st.cache_data
def clean_data(df):
    df = df.copy()
    
    critical_columns = ['price', 'title', 'rating']
    df = df.dropna(subset=critical_columns)
    
    df = df.assign(
        description=df['description'].fillna('No description'),
        num_reviews=df['num_reviews'].fillna(0)
    )
    
    df = df.drop_duplicates()
    
    price_columns = ['price', 'price_excl_tax', 'price_incl_tax', 'tax']
    for col in price_columns:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notnull(x) else 0.0)
    
    rating_map = {'One': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5}
    df['rating'] = df['rating'].map(rating_map).fillna(3)
    
    df['availability'] = df['availability'].astype(int)
    
    df['description'] = df['description'].str.strip()
    
    df['num_reviews'] = df['num_reviews'].astype(int)
    
    return df

if scrape_button:
    books_df = scrape_books(pages_to_scrape)
    st.session_state.books_df = books_df
    st.session_state.cleaned_df = clean_data(books_df)
    st.success("Data successfully scraped and cleaned!")
elif 'cleaned_df' not in st.session_state:
    st.warning("Using cached data. Click 'Scrape Fresh Data' to get new data.")
    books_df = scrape_books(pages_to_scrape)
    st.session_state.books_df = books_df
    st.session_state.cleaned_df = clean_data(books_df)

cleaned_df = st.session_state.cleaned_df

tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Visual Analysis", "📚 Book Explorer", "💾 Data"])

with tab1:
    st.header("Dataset Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Books", len(cleaned_df))
    with col2:
        st.metric("Average Price", f"£{cleaned_df['price'].mean():.2f}")
    with col3:
        st.metric("Total Available", cleaned_df['availability'].sum())
    with col4:
        st.metric("Average Rating", f"{cleaned_df['rating'].mean():.1f} ★")
    
    st.subheader("Sample Data")
    st.dataframe(cleaned_df.head(10), use_container_width=True)
    
    st.subheader("Data Summary")
    st.dataframe(cleaned_df.describe(), use_container_width=True)

with tab2:
    st.header("📊 Visual Analysis")
    
    sns.set_theme(style="whitegrid")
    plt.style.use('ggplot')
    
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Price Distribution")
            fig1, ax1 = plt.subplots(figsize=(10, 6))
            sns.histplot(cleaned_df['price'], bins=20, kde=True, ax=ax1)
            ax1.set_title('Distribution of Book Prices', fontsize=14)
            ax1.set_xlabel('Price (£)', fontsize=12)
            ax1.set_ylabel('Count', fontsize=12)
            st.pyplot(fig1)
    
    with col2:
        with st.container(border=True):
            st.subheader("Rating Distribution")
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            sns.countplot(x='rating', data=cleaned_df, ax=ax2, order=sorted(cleaned_df['rating'].unique()))
            ax2.set_title('Distribution of Book Ratings', fontsize=14)
            ax2.set_xlabel('Rating (1-5)', fontsize=12)
            ax2.set_ylabel('Count', fontsize=12)
            st.pyplot(fig2)
    
    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            st.subheader("Price by Rating")
            fig3, ax3 = plt.subplots(figsize=(10, 6))
            sns.boxplot(x='rating', y='price', data=cleaned_df, ax=ax3, 
                        order=sorted(cleaned_df['rating'].unique()))
            ax3.set_title('Book Prices by Rating Level', fontsize=14)
            ax3.set_xlabel('Rating (1-5)', fontsize=12)
            ax3.set_ylabel('Price (£)', fontsize=12)
            st.pyplot(fig3)
    
    with col4:
        with st.container(border=True):
            st.subheader("Availability vs Price")
            fig4, ax4 = plt.subplots(figsize=(10, 6))
            scatter = sns.scatterplot(x='availability', y='price', data=cleaned_df, 
                                    hue='rating', palette='viridis', size='rating', 
                                    sizes=(50, 200), ax=ax4)
            ax4.set_title('Availability vs Price by Rating', fontsize=14)
            ax4.set_xlabel('Number Available', fontsize=12)
            ax4.set_ylabel('Price (£)', fontsize=12)
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            st.pyplot(fig4)

with tab3:
    st.header("Book Explorer")
    
    col1, col2 = st.columns(2)
    with col1:
        search_term = st.text_input("Search books by title or description")
    with col2:
        rating_filter = st.multiselect(
            "Filter by rating",
            options=sorted(cleaned_df['rating'].unique()),
            default=sorted(cleaned_df['rating'].unique())
        )
    
    price_range = st.slider(
        "Price range (£)",
        float(cleaned_df['price'].min()),
        float(cleaned_df['price'].max()),
        (float(cleaned_df['price'].min()), float(cleaned_df['price'].max()))
    )
    
    filtered_df = cleaned_df[
        (cleaned_df['price'] >= price_range[0]) & 
        (cleaned_df['price'] <= price_range[1]) &
        (cleaned_df['rating'].isin(rating_filter))
    ]
    
    if search_term:
        filtered_df = filtered_df[
            filtered_df['title'].str.contains(search_term, case=False) |
            filtered_df['description'].str.contains(search_term, case=False)
        ]
    
    st.subheader(f"Found {len(filtered_df)} books matching your criteria")
    
    for _, row in filtered_df.iterrows():
        with st.expander(f"{row['title']} - £{row['price']:.2f} | Rating: {'★' * row['rating']}"):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.metric("Price", f"£{row['price']:.2f}")
                st.metric("Rating", f"{row['rating']} ★")
                st.metric("Available", row['availability'])
            with col2:
                st.write(f"**Description:** {row['description']}")
                st.caption(f"**Product Type:** {row['product_type']} | **Reviews:** {row['num_reviews']} | **UPC:** {row['upc']}")

with tab4:
    st.header("Raw Data")
    
    st.download_button(
        label="Download Cleaned Data as CSV",
        data=cleaned_df.to_csv(index=False).encode('utf-8'),
        file_name='cleaned_books_data.csv',
        mime='text/csv'
    )
    
    st.dataframe(cleaned_df, use_container_width=True)
    
    st.subheader("Data Cleaning Report")
    st.markdown("""
    - **Null Values Handled**: Dropped rows with null prices, titles or ratings. Filled null descriptions with 'No description'.
    - **Duplicates Removed**: All duplicate rows were removed from the dataset.
    - **Price Columns Cleaned**: Removed non-numeric characters and converted to float.
    - **Ratings Converted**: Text ratings (One-Five) converted to numerical (1-5).
    - **Availability**: Extracted numbers from availability text during scraping.
    """)
