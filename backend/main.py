"""
Flask Backend API for Partner Level Breakdown Dashboard - Main Application

This is the main application file that:
1. Sets up Flask app and shared utilities
2. Loads and manages partner data
3. Provides health checks and shared endpoints
4. Imports and registers routes from tab-specific modules
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import traceback
import json
import pandas as pd
import os
from datetime import datetime
import numpy as np
from collections import OrderedDict
import random
from dotenv import load_dotenv
from db_integration import db
# Region mapping removed - only used in partner_overview.py for region filtering

# Import route modules
from partner_overview import register_partner_overview_routes
from country_analysis import register_country_analysis_routes
from partner_management import register_partner_management_routes

# Load environment variables
load_dotenv()

# Set up Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for data
partner_data = None
csv_files_loaded = False
backend_ready = False

def load_csv_data():
    """Load partner data from CSV files"""
    global partner_data, csv_files_loaded

    try:
        logger.info("🚀 Starting CSV data loading process...")
        csv_files = ['Quarter 1.csv', 'Quarter 2.csv', 'Quarter 3.csv']
        # Try both relative paths depending on where the script is run from
        possible_data_dirs = ['../data', './data', '/Users/manaskarra/Desktop/Work/PDash/data']
        data_dir = None

        for dir_path in possible_data_dirs:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                data_dir = dir_path
                break

        if not data_dir:
            raise FileNotFoundError(f"Data directory not found. Tried: {possible_data_dirs}")

        logger.info(f"📁 Using data directory: {data_dir}")
        all_data = []

        for i, csv_file in enumerate(csv_files, 1):
            logger.info(f"📊 Loading file {i}/{len(csv_files)}: {csv_file}...")
            file_path = os.path.join(data_dir, csv_file)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_data.append(df)
                logger.info(f"✅ Loaded {csv_file} with {len(df):,} records")
            else:
                logger.warning(f"❌ CSV file not found: {file_path}")

        if all_data:
            logger.info("🔄 Concatenating all data files...")
            partner_data = pd.concat(all_data, ignore_index=True)
            csv_files_loaded = True
            logger.info(f"📈 Total partner records loaded: {len(partner_data):,}")

            # Clean and standardize data
            logger.info("🧹 Starting data standardization...")
            standardize_data()
            
            # Mark backend as ready
            global backend_ready
            backend_ready = True
            logger.info("🎉 Backend is now ready to serve requests!")
            logger.info("✅ CSV data loading completed successfully!")
        else:
            error_msg = f"No CSV files found in {data_dir} directory. Required files: Quarter 1.csv, Quarter 2.csv, Quarter 3.csv"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

    except Exception as e:
        error_msg = f"❌ Error loading CSV data: {str(e)}"
        logger.error(error_msg)
        raise e

def standardize_data():
    """Clean and standardize the loaded data"""
    global partner_data

    try:
        # Standardize column names
        partner_data.columns = partner_data.columns.str.lower().str.replace(' ', '_')

        # Convert date columns
        date_columns = ['joined_date', 'month']
        for col in date_columns:
            if col in partner_data.columns:
                partner_data[col] = pd.to_datetime(partner_data[col], errors='coerce')

        # Convert numeric columns
        numeric_columns = ['avg_past_3_months_earnings', 'total_earnings',
                          'company_revenue', 'active_clients', 'new_active_clients', 'volume_usd', 'total_deposits']
        for col in numeric_columns:
            if col in partner_data.columns:
                partner_data[col] = pd.to_numeric(partner_data[col], errors='coerce')

        # Fill NaN values
        partner_data.fillna({
            'partner_tier': 'Bronze',
            'avg_past_3_months_earnings': 0,
            'total_earnings': 0,
            'company_revenue': 0,
            'active_clients': 0,
            'new_active_clients': 0,
            'volume_usd': 0,
            'total_deposits': 0,
            'is_app_dev': False
        }, inplace=True)

        # UPDATED: Assign "Inactive" tier to partners with 0 total earnings
        # Group by partner_id and check total earnings across all months
        partner_total_earnings = partner_data.groupby('partner_id')['total_earnings'].sum().reset_index()
        partner_total_earnings.columns = ['partner_id', 'cumulative_earnings']

        # Find partners with 0 cumulative earnings
        inactive_partners = partner_total_earnings[partner_total_earnings['cumulative_earnings'] == 0]['partner_id'].tolist()

        # Update tier to "Inactive" for partners with 0 earnings
        partner_data.loc[partner_data['partner_id'].isin(inactive_partners), 'partner_tier'] = 'Inactive'

        # Fetch GP regions mapping from Supabase and apply to partner data
        logger.info("🌍 Fetching GP region mappings from database...")
        try:
            gp_regions_mapping = db.get_partner_regions_mapping()
            if gp_regions_mapping:
                logger.info(f"📍 Applying GP region mapping to partner data...")
                # Create a new column for GP regions
                partner_data['gp_region'] = partner_data['partner_id'].astype(str).map(gp_regions_mapping)
                # Replace the original region with GP region where available, keep original as fallback
                partner_data['region'] = partner_data['gp_region'].fillna(partner_data['region'])
                # Drop the temporary gp_region column
                partner_data.drop('gp_region', axis=1, inplace=True)
                logger.info(f"✅ Applied GP region mapping to {len([v for v in gp_regions_mapping.values() if v]):,} partners")
            else:
                logger.warning("⚠️ No GP region mapping retrieved from database, keeping original CSV regions")
        except Exception as e:
            logger.error(f"❌ Error applying GP region mapping: {str(e)}, keeping original CSV regions")

        logger.info(f"✅ Data standardization completed. {len(inactive_partners):,} partners marked as Inactive (0 earnings)")

    except Exception as e:
        logger.error(f"Error standardizing data: {str(e)}")
        raise e

def get_partner_data():
    """Get current partner data (for passing to modules)"""
    global partner_data
    return partner_data

# Health endpoints (shared)
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Get database health status
        db_health = db.health_check()

        return jsonify({
            'status': 'healthy' if db_health['status'] == 'healthy' else 'degraded',
            'csv_loaded': csv_files_loaded,
            'partner_count': len(partner_data) if partner_data is not None else 0,
            'database': db_health,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'csv_loaded': csv_files_loaded,
            'partner_count': len(partner_data) if partner_data is not None else 0,
            'database': {'status': 'unhealthy', 'error': str(e)},
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/db-health', methods=['GET'])
def database_health_check():
    """Dedicated database health check endpoint"""
    try:
        db_health = db.health_check()
        return jsonify(db_health)
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': None,
            'server_time': None,
            'pool_status': {
                'available_connections': 0,
                'used_connections': 0
            }
        }), 500

@app.route('/api/ready', methods=['GET'])
def readiness_check():
    """Backend readiness endpoint - returns ready only when all data is loaded and processed"""
    try:
        global backend_ready, csv_files_loaded, partner_data
        
        if backend_ready and csv_files_loaded and partner_data is not None:
            return jsonify({
                'ready': True,
                'status': 'Backend is ready to serve requests',
                'data_loaded': True,
                'total_records': len(partner_data),
                'data_processing_complete': True,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'ready': False,
                'status': 'Backend is still loading data...',
                'data_loaded': csv_files_loaded,
                'total_records': len(partner_data) if partner_data is not None else 0,
                'data_processing_complete': backend_ready,
                'timestamp': datetime.now().isoformat()
            }), 503  # Service Unavailable
            
    except Exception as e:
        return jsonify({
            'ready': False,
            'status': 'Backend initialization error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/filters', methods=['GET'])
def get_filter_options():
    """Get available filter options"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400

        # UPDATED: Define proper tier hierarchy order including Inactive
        tier_hierarchy = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
        available_tiers = partner_data['partner_tier'].dropna().unique().tolist()
        # Keep only existing tiers in hierarchy order
        ordered_tiers = [tier for tier in tier_hierarchy if tier in available_tiers]

        filters = {
            'countries': sorted(partner_data['country'].dropna().unique().tolist()),
            'regions': sorted(partner_data['region'].dropna().unique().tolist()),
            'tiers': ordered_tiers,
            'months': sorted(partner_data['month'].dt.strftime('%Y-%m').unique().tolist())
        }

        return jsonify(filters)

    except Exception as e:
        logger.error(f"Error getting filter options: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics', methods=['POST'])
def get_analytics():
    """Get analytics data based on query"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400

        query_data = request.get_json()
        query_text = query_data.get('query', '').lower()

        # Simple analytics based on query
        if 'top partners' in query_text:
            top_partners = partner_data.nlargest(10, 'total_earnings')[
                ['partner_id', 'first_name', 'last_name', 'country', 'total_earnings', 'partner_tier']
            ].to_dict('records')

            response = {
                'type': 'top_partners',
                'data': top_partners,
                'message': 'Here are the top 10 partners by total earnings:'
            }

        elif 'revenue by country' in query_text:
            country_revenue = partner_data.groupby('country')['total_earnings'].sum().sort_values(ascending=False).to_dict()

            response = {
                'type': 'country_revenue',
                'data': country_revenue,
                'message': 'Revenue breakdown by country:'
            }

        elif 'tier distribution' in query_text:
            tier_dist = partner_data['partner_tier'].value_counts().to_dict()

            response = {
                'type': 'tier_distribution',
                'data': tier_dist,
                'message': 'Partner tier distribution:'
            }

        else:
            response = {
                'type': 'general',
                'data': None,
                'message': 'I can help you analyze partner data. Try asking about "top partners", "revenue by country", or "tier distribution".'
            }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Register routes from modules
register_partner_overview_routes(app, get_partner_data)
register_country_analysis_routes(app, get_partner_data)
register_partner_management_routes(app, get_partner_data)

# Initialize data on startup
load_csv_data()

# Graceful shutdown handler
import atexit
import signal

def graceful_shutdown(signum=None, frame=None):
    """Handle graceful shutdown of the application"""
    logger.info("Shutting down application...")
    try:
        db.disconnect()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# Register shutdown handlers
atexit.register(graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)

if __name__ == '__main__':
    logger.info("Starting PDash backend server...")
    logger.info("Database connection pool initialized successfully")
    app.run(debug=True, host='0.0.0.0', port=5003)