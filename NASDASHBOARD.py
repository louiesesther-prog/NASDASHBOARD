import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import plotly.express as px

# --- 1. DASHBOARD CONFIG ---
st.set_page_config(page_title="NAS100 Quant Tracker", layout="wide")
st.title("🚀 NAS100 (NQ=F) Volume Spike Analysis")
st.markdown("Tracking tech-heavy institutional moves in **Non-US** vs **US** Sessions.")

# --- 2. DATA FETCHING (NAS100 Optimized) ---
@st.cache_data(ttl=600)
def get_nas_data():
    # Attempt 1: NQ Futures (NQ=F)
    # Attempt 2: Nasdaq-100 Index (^NDX)
    for ticker in ['NQ=F', '^NDX']:
        try:
            df_raw = yf.download(tickers=ticker, period='60d', interval='15m', progress=False)
            if not df_raw.empty and len(df_raw) > 20:
                if isinstance(df_raw.columns, pd.MultiIndex):
                    df_raw.columns = df_raw.columns.get_level_values(0)
                
                df = df_raw.reset_index()
                df.columns.values[0] = 'timestamp'
                df.columns = [str(col).lower() for col in df.columns]
                
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
                
                # Session Logic (EST)
                df['hour'] = df['timestamp'].dt.hour
                df['session'] = np.where(df['hour'].between(9, 16), "US Session", "Non-US Session")
                return df, ticker
        except Exception:
            continue
    return pd.DataFrame(), None

# --- 3. QUANT LOGIC ---
try:
    df, active_ticker = get_nas_data()

    if df.empty:
        st.error("🚨 NAS100 data currently unavailable from Yahoo Finance.")
    else:
        st.sidebar.success(f"Viewing: {active_ticker}")
        
        # Sidebar Settings
        st.sidebar.header("NAS100 Settings")
        session_choice = st.sidebar.multiselect(
            "Filter Sessions", 
            options=["US Session", "Non-US Session"], 
            default=["US Session", "Non-US Session"]
        )
        
        z_thresh = st.sidebar.slider("Volume Sensitivity", 1.5, 6.0, 3.5)
        
        # Rolling Z-Score for Volume
        df['vol_mean'] = df['volume'].rolling(window=20).mean()
        df['vol_std'] = df['volume'].rolling(window=20).std()
        df['z_score'] = (df['volume'] - df['vol_mean']) / df['vol_std']
        
        # Identify Spikes
        df['is_spike'] = (df['z_score'] > z_thresh) & (df['session'].isin(session_choice))
        spikes_df = df[df['is_spike']].copy()

        # --- 4. THE UI ---
        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader(f"Nasdaq 15m Chart")
            fig = go.Figure(data=[go.Candlestick(
                x=df['timestamp'],
                open=df['open'], high=df['high'],
                low=df['low'], close=df['close'],
                name="NAS100"
            )])

            fig.add_trace(go.Scatter(
                x=spikes_df['timestamp'],
                y=spikes_df['high'] * 1.001,
                mode='markers',
                marker=dict(color='#00F2FF', size=10, symbol='triangle-down'),
                name="Spike"
            ))

            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
            st.plotly_chart(fig, width="stretch")

        with col2:
            st.subheader("📋 Data Log")
            if not spikes_df.empty:
                spikes_df['time'] = spikes_df['timestamp'].dt.strftime('%H:%M')
                spikes_df['date'] = spikes_df['timestamp'].dt.strftime('%Y-%m-%d')
                st.dataframe(
                    spikes_df[['date', 'time', 'session', 'z_score']].sort_values(by='date', ascending=False),
                    width="stretch", height=550
                )
            else:
                st.info("Adjust sensitivity to see patterns.")

        # --- 5. SEASONALITY ---
        st.divider()
        if not spikes_df.empty:
            st.subheader("📈 NAS100 Time-of-Day Uniformity")
            pattern_freq = spikes_df.groupby(['time', 'session']).size().reset_index(name='count')
            
            freq_fig = px.bar(
                pattern_freq, x='time', y='count', color='session',
                barmode='group',
                color_discrete_map={"US Session": "#00F2FF", "Non-US Session": "#FF007F"}
            )
            freq_fig.update_layout(template="plotly_dark")
            st.plotly_chart(freq_fig, width="stretch")

except Exception as e:
    st.error(f"Logic Error: {e}")
