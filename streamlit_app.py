import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import pyodbc
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

DB_CONFIG = {
    'server': 'DESKTOP-O0HMMLT',
    'database': 'DS_Tools_Project',
    'driver': 'ODBC Driver 17 for SQL Server'
}

st.set_page_config(
    page_title="Books Analysis Dashboard",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_db_connection():
    """Create and return a database connection."""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def scrape_books(pages_to_scrape=2):
    """Scrape book data from books.toscrape.com."""
    base_url = "http://books.toscrape.com/"
    all_books = []

    for page in range(1, pages_to_scrape + 1):
        print(f"Scraping page {page}...")
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
            availability = int(availability_match.group(1)) if availability_match else (
                1 if 'In stock' in availability_text else 0)

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



def clean_data(df):
    """Clean and preprocess the scraped book data."""
    df = df.copy()

    # Handle null values
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


def analyze_data(df):
    """Perform basic analysis on the cleaned data."""
    analysis_results = {
        'average_price': df['price'].mean(),
        'max_price': df['price'].max(),
        'min_price': df['price'].min(),
        'total_available': df['availability'].sum(),
        'rating_distribution': df['rating'].value_counts().sort_index(),
        'price_by_rating': df.groupby('rating')['price'].mean()
    }
    return analysis_results


def save_to_database(df):
    """Save cleaned data to SQL Server database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Books' AND xtype='U')
        CREATE TABLE Books (
            ID INT IDENTITY(1,1) PRIMARY KEY,
            Title NVARCHAR(255),
            Price FLOAT,
            Rating INT,
            Availability INT,
            UPC NVARCHAR(50),
            ProductType NVARCHAR(100),
            PriceExclTax FLOAT,
            PriceInclTax FLOAT,
            Tax FLOAT,
            NumReviews INT,
            Description NVARCHAR(MAX),
            DateAdded DATETIME DEFAULT GETDATE()
        )
        """)
        conn.commit()

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO Books (
                    Title, Price, Rating, Availability, UPC, ProductType,
                    PriceExclTax, PriceInclTax, Tax, NumReviews, Description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                           row['title'], row['price'], row['rating'], row['availability'],
                           row['upc'], row['product_type'], row['price_excl_tax'],
                           row['price_incl_tax'], row['tax'], row['num_reviews'],
                           row['description']
                           )

        conn.commit()
        print(f"Successfully inserted {len(df)} records into the database")

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


def show_dashboard(cleaned_df):
    """Display the Streamlit dashboard with the cleaned data."""
    st.title("📚 Books to Scrape Analysis Dashboard")
    st.markdown("""
    This interactive dashboard analyzes book data scraped from [books.toscrape.com](http://books.toscrape.com/).
    Explore pricing, ratings, availability, and more!
    """)

    st.sidebar.header("Controls")
    pages_to_scrape = st.sidebar.slider("Number of pages to scrape", 1, 5, 2)
    scrape_button = st.sidebar.button("Scrape Fresh Data")

    if scrape_button:
        with st.spinner("Scraping fresh data..."):
            books_df = scrape_books(pages_to_scrape)
            cleaned_df = clean_data(books_df)
            save_to_database(cleaned_df)
            st.session_state.cleaned_df = cleaned_df
            st.success("Data successfully scraped, cleaned, and saved to database!")

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

    with tab2:
        st.header("📊 Visual Analysis")
        sns.set_theme(style="whitegrid")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Price Distribution")
            fig1 = plt.figure(figsize=(10, 6))
            sns.histplot(cleaned_df['price'], bins=20, kde=True)
            st.pyplot(fig1)

        with col2:
            st.subheader("Rating Distribution")
            fig2 = plt.figure(figsize=(10, 6))
            sns.countplot(x='rating', data=cleaned_df)
            st.pyplot(fig2)

        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Price by Rating")
            fig3 = plt.figure(figsize=(10, 6))
            sns.boxplot(x='rating', y='price', data=cleaned_df)
            st.pyplot(fig3)

        with col4:
            st.subheader("Availability vs Price")
            fig4 = plt.figure(figsize=(10, 6))
            sns.scatterplot(x='availability', y='price', data=cleaned_df, hue='rating')
            st.pyplot(fig4)

    with tab3:
        st.header("Book Explorer")
        search_term = st.text_input("Search books by title or description")
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
                    st.caption(f"**Product Type:** {row['product_type']} | **Reviews:** {row['num_reviews']}")

    with tab4:
        st.header("Raw Data")
        st.download_button(
            label="Download Cleaned Data as CSV",
            data=cleaned_df.to_csv(index=False).encode('utf-8'),
            file_name='cleaned_books_data.csv',
            mime='text/csv'
        )
        st.dataframe(cleaned_df, use_container_width=True)


def main():
    """Main execution function."""
    if 'cleaned_df' not in st.session_state:
        with st.spinner("Loading initial data..."):
            books_df = scrape_books()
            cleaned_df = clean_data(books_df)
            save_to_database(cleaned_df)
            st.session_state.cleaned_df = cleaned_df

    show_dashboard(st.session_state.cleaned_df)


if __name__ == "__main__":
    main()
