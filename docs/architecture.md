# 🏗️ Architecture

TraderMagic is built with a modern, service-based architecture that separates concerns and provides flexibility.

## 🧩 Components

The system consists of four main services that work together:

### 📡 Data Retrieval Service

**Purpose**: Fetches technical indicators from external APIs  
**Key Features**:
- Polls TAAPI.io for RSI (Relative Strength Index) data
- Rate-limiting to respect API constraints
- Caches results in Redis for other services

**Technology**:
- Python async HTTP client
- TAAPI.io API integration
- Configurable polling intervals

### 🧠 AI Decision Engine

**Purpose**: Analyzes market data and makes trading decisions  
**Key Features**:
- Uses locally-run Ollama LLM to analyze RSI data
- Determines whether to buy, sell, or hold based on analysis
- Explains reasoning behind each decision

**Technology**:
- Ollama integration for local LLM inference
- Prompt engineering for financial analysis
- Redis for receiving data and publishing decisions

### 💹 Trade Execution Service

**Purpose**: Executes trades based on AI decisions  
**Key Features**:
- Connects to Alpaca for trade execution
- Implements trade amount calculation
- Handles order placement and tracking
- Respects trading enabled/disabled flag

**Technology**:
- Alpaca API integration
- Portfolio management logic
- Trading safeguards and limits

### 🖥️ Web Dashboard

**Purpose**: User interface for monitoring and control  
**Key Features**:
- Real-time trade monitoring
- Trading control interface
- Trade mode configuration
- Theme customization

**Technology**:
- Flask for backend API
- Socket.IO for real-time updates
- Responsive frontend design

## 🔄 Data Flow

1. **Data Retrieval Service** polls TAAPI.io for RSI data
2. Data is stored in Redis with symbol-specific keys
3. **AI Decision Engine** consumes RSI data and generates trade signals
4. Signals are stored in Redis with corresponding keys
5. **Trade Execution Service** processes signals and executes trades
6. Trade results are stored in Redis
7. **Web Dashboard** displays all data from Redis in real-time

## 📦 Containerization

All components are containerized using Docker:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Data Retrieval  │    │  AI Decision    │    │Trade Execution  │
│    Service      │    │    Engine       │    │    Service      │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │                      ▼                      │
         │             ┌─────────────────┐             │
         └────────────►│      Redis      │◄────────────┘
                       │                 │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Web Dashboard  │
                       │                 │
                       └─────────────────┘
```

Each service can be scaled independently and communicates via Redis.