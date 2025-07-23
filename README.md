# Partner Dashboard

A modern, responsive partner management dashboard built with React frontend and Flask backend, featuring real-time analytics, AI-powered insights, and comprehensive partner performance tracking.

## 🚀 Features

- **Partner Management**: Complete partner lifecycle management with filtering and search
- **Real-time Analytics**: Live tier performance breakdown and commission analytics  
- **Modern UI**: Responsive design with Deriv branding and smooth animations
- **AI Insights**: Intelligent analysis and recommendations powered by AI
- **Performance Tracking**: Monthly performance metrics and trend analysis
- **Custom Loading**: Beautiful branded loading screens
- **Data Visualization**: Interactive charts and tier contribution overviews

## 🏗️ Architecture

### Frontend (React)
- Modern React application with hooks and components
- Responsive CSS with custom design system
- Interactive charts using Recharts
- AI-powered insights integration
- Custom loading screens and animations

### Backend (Flask)
- RESTful API with Flask
- CSV data processing with Pandas
- AI integration with LangChain and OpenAI
- Real-time analytics calculations
- Comprehensive partner filtering

## 📋 Prerequisites

- **Backend**: Python 3.12+
- **Frontend**: Node.js 16+ and npm
- **Database**: CSV files (Quarter 1.csv, Quarter 2.csv, Quarter 3.csv)
- **AI Features**: OpenAI API key (optional)

## 🛠️ Installation

### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. Start the Flask server:
   ```bash
   python main.py
   ```

### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

## 📊 Data Setup

1. Create a `data/` folder in the project root
2. Add your CSV files:
   - `Quarter 1.csv`
   - `Quarter 2.csv` 
   - `Quarter 3.csv`

**Note**: If no CSV files are found, the application will generate sample data for development.

## 🔧 Configuration

### Environment Variables (.env)

```bash
# AI Features (Optional)
OPENAI_API_KEY=your_openai_api_key_here
API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-3.5-turbo

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
```

## 🚀 Usage

1. **Access the Dashboard**: Navigate to `http://localhost:3000`
2. **API Endpoints**: Backend available at `http://localhost:5002`
3. **Partner Management**: Use filters to find and analyze partners
4. **AI Insights**: Get intelligent recommendations and analysis
5. **Performance Tracking**: Monitor tier progression and earnings

## 📖 API Endpoints

- `GET /api/health` - Health check
- `GET /api/partner-overview` - Dashboard overview metrics
- `GET /api/partners` - Paginated partner list with filtering
- `GET /api/partners/{id}` - Individual partner details
- `GET /api/tier-analytics` - Tier performance breakdown
- `GET /api/filters` - Available filter options
- `POST /api/ai-insights` - AI-powered insights generation

## 🎨 Key Components

### Frontend Components
- **Dashboard**: Main dashboard layout and orchestration
- **PartnerTable**: Sortable, filterable partner data table
- **TierAnalytics**: Interactive tier performance charts
- **LoadingScreen**: Branded loading experience
- **AICopilot**: AI insights and recommendations

### Backend Features
- **Partner Data Processing**: CSV parsing and aggregation
- **Real-time Analytics**: Dynamic tier performance calculations
- **AI Integration**: LangChain-powered insights generation
- **Filtering & Search**: Advanced partner filtering capabilities

## 🔒 Security

- Environment variables for sensitive data
- .gitignore properly configured
- No credentials in source code
- Secure API key handling

## 📱 Responsive Design

- Mobile-first approach
- Adaptive layouts for all screen sizes
- Touch-friendly interface
- Modern CSS with smooth animations

## 🤖 AI Features

- Intelligent dashboard insights
- Partner performance analysis
- Trend identification and recommendations
- Natural language explanations

## 🚢 Deployment

### Backend
```bash
# Production WSGI server recommended
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5002 main:app
```

### Frontend
```bash
npm run build
# Deploy build/ folder to your web server
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🏢 Built for Deriv

This dashboard is specifically designed for Deriv's partner management needs, featuring:
- Deriv branding and design system
- Partner tier management (Platinum, Gold, Silver, Bronze)
- Commission and revenue tracking
- API developer identification
- Multi-region support

---

**Note**: For production deployment, ensure all environment variables are properly configured and sensitive data is excluded from version control. 