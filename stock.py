import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from dotenv import load_dotenv
from groq import Groq
from duckduckgo_search import DDGS
import google.generativeai as genai

# Explicitly load .env file
load_dotenv(override=True)

class StockAnalysisApp:
    def __init__(self):
        # Initialize session state variables
        if 'ticker' not in st.session_state:
            st.session_state.ticker = 'NVDA'
        
        st.set_page_config(page_title="Stock Analysis Dashboard", page_icon="📈", layout="wide")
        
        # Initialize API keys
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        # Configure Gemini
        genai.configure(api_key=self.gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def fetch_stock_data(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            
            # Fetch historical data
            hist_data = stock.history(period="1y")
            
            # Fetch info with error handling
            try:
                info = stock.info
                if not info:
                    st.error(f"No data found for ticker: {ticker}")
                    return None
            except Exception as e:
                st.error(f"Error fetching stock info: {e}")
                return None

            # Fetch recommendations
            try:
                recommendations = stock.recommendations
            except Exception:
                recommendations = pd.DataFrame()

            # Fetch news using DuckDuckGo
            ddgs = DDGS()
            ddg_news = list(ddgs.news(f"{info.get('longName', ticker)} stock news", max_results=10))

            return {
                'Basic Info': {
                    'Company Name': info.get('longName', 'N/A'),
                    'Sector': info.get('sector', 'N/A'),
                    'Industry': info.get('industry', 'N/A'),
                    'Market Cap': f"${info.get('marketCap', 'N/A'):,}",
                },
                'Current Price': {
                    'Current': info.get('currentPrice', 'N/A'),
                    '52 Week High': info.get('fiftyTwoWeekHigh', 'N/A'),
                    '52 Week Low': info.get('fiftyTwoWeekLow', 'N/A'),
                },
                'Financial Health': {
                    'P/E Ratio': info.get('trailingPE', 'N/A'),
                    'Dividend Yield': f"{info.get('dividendYield', 'N/A')*100:.2f}%" if info.get('dividendYield') else 'N/A',
                    'ROE': f"{info.get('returnOnEquity', 'N/A')*100:.2f}%" if info.get('returnOnEquity') else 'N/A',
                },
                'Recommendations': recommendations.tail(5) if not recommendations.empty else pd.DataFrame(),
                'Historical Data': hist_data,
                'News': ddg_news
            }
        except Exception as e:
            st.error(f"Unexpected error fetching stock data: {e}")
            return None

    def generate_gemini_analysis(self, stock_data, news):
        try:
            # Prepare concise prompt for Gemini
            news_summary = "\n".join([
                f"Title: {article.get('title', 'N/A')}"
                for article in news[:3]  # Limit to top 3 news articles
            ])

            prompt = f"""Provide a concise stock analysis and decision recommendation based on the following information:

Company Details:
- Name: {stock_data['Basic Info']['Company Name']}
- Sector: {stock_data['Basic Info']['Sector']}
- Market Cap: {stock_data['Basic Info']['Market Cap']}

Financial Metrics:
- Current Price: {stock_data['Current Price']['Current']}
- P/E Ratio: {stock_data['Financial Health']['P/E Ratio']}
- Dividend Yield: {stock_data['Financial Health']['Dividend Yield']}

Recent News Headlines:
{news_summary}

Analysis Requirements:
1. Provide a **clear decision recommendation** (Buy/Hold/Sell) in the first line.
2. Summarize the **key reasons** for the recommendation in 2-3 bullet points.
3. Keep the analysis concise and focused on actionable insights."""

            # Generate analysis using Gemini
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=500  # Limit output length
                )
            )
            return response.text
        except Exception as e:
            return f"❌ Gemini Analysis Error: {str(e)}"

    def display_dashboard(self):
        st.title("📈 Advanced Stock Analysis Dashboard with AI Decision Support")
        
        st.sidebar.header("Stock Selector")
        st.session_state.ticker = st.sidebar.text_input(
            "Enter Stock Ticker", 
            value=st.session_state.ticker
        )
        
        analysis_type = st.sidebar.radio(
            "Select Analysis Type",
            ["Overview", "Price Charts", "AI Decision Support"]
        )
        
        if st.sidebar.button("Analyze Stock"):
            stock_data = self.fetch_stock_data(st.session_state.ticker)
            
            if stock_data:
                if analysis_type == "Overview":
                    self.display_overview_section(stock_data)
                elif analysis_type == "Price Charts":
                    self.display_price_charts(stock_data)
                else:
                    self.display_ai_decision_support(stock_data)

    def display_overview_section(self, stock_data):
        st.header(f"Company Overview: {stock_data['Basic Info']['Company Name']}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sector", stock_data['Basic Info']['Sector'])
        with col2:
            st.metric("Market Cap", stock_data['Basic Info']['Market Cap'])
        with col3:
            st.metric("Industry", stock_data['Basic Info'].get('Industry', 'N/A'))
        
        st.subheader("Price Performance")
        price_cols = st.columns(3)
        price_metrics = stock_data['Current Price']
        for i, (key, value) in enumerate(price_metrics.items()):
            price_cols[i].metric(key, value)
        
        st.subheader("Financial Health")
        fin_cols = st.columns(3)
        fin_metrics = stock_data['Financial Health']
        for i, (key, value) in enumerate(fin_metrics.items()):
            fin_cols[i].metric(key, value)
        
        st.subheader("Recent Analyst Recommendations")
        if not stock_data['Recommendations'].empty:
            st.dataframe(stock_data['Recommendations'])
        else:
            st.write("No recent recommendations available")

    def display_ai_decision_support(self, stock_data):
        st.header(f"AI Decision Support: {stock_data['Basic Info']['Company Name']}")
        
        # Display News
        st.subheader("Recent News")
        for article in stock_data['News'][:3]:  # Show only top 3 news articles
            st.markdown(f"""
            **{article.get('title', 'No Title')}**
            
            Source: {article.get('source', 'Unknown')}
            
            [Read More]({article.get('url', '#')})
            
            ---
            """)
        
        # Generate Gemini AI Analysis
        st.subheader("AI Agent Investment Insights")
        with st.spinner('Generating AI-powered decision support...'):
            ai_analysis = self.generate_gemini_analysis(stock_data, stock_data['News'])
        
        # Format the output
        if "❌" not in ai_analysis:  # Check for errors
            st.markdown("### Decision Recommendation")
            lines = ai_analysis.split("\n")
            st.success(lines[0])  # Highlight the decision (e.g., Buy/Hold/Sell)
            
            st.markdown("### Key Reasons")
            for line in lines[1:]:
                if line.strip():  # Skip empty lines
                    st.write(f"- {line.strip()}")
        else:
            st.error(ai_analysis)  # Display error message if any

    def display_price_charts(self, stock_data):
        st.header(f"Price Analysis: {stock_data['Basic Info']['Company Name']}")
        
        # Price Chart
        st.subheader("Stock Price Movement")
        price_chart = self.plot_stock_price(stock_data['Historical Data'])
        st.plotly_chart(price_chart)
        
        # Volume Chart
        st.subheader("Trading Volume")
        volume_chart = self.plot_volume_chart(stock_data['Historical Data'])
        st.plotly_chart(volume_chart)

    def plot_stock_price(self, hist_data):
        # Create interactive price chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=hist_data.index,
            open=hist_data['Open'],
            high=hist_data['High'],
            low=hist_data['Low'],
            close=hist_data['Close'],
            name='Price'
        ))
        fig.update_layout(
            title='Stock Price Movement',
            xaxis_title='Date',
            yaxis_title='Price',
            xaxis_rangeslider_visible=False
        )
        return fig

    def plot_volume_chart(self, hist_data):
        # Create volume chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=hist_data.index,
            y=hist_data['Volume'],
            name='Volume'
        ))
        fig.update_layout(
            title='Trading Volume',
            xaxis_title='Date',
            yaxis_title='Volume'
        )
        return fig

    def run(self):
        self.display_dashboard()

# Main execution
if __name__ == "__main__":
    app = StockAnalysisApp()
    app.run()