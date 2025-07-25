"""
Flask Backend API for Partner Level Breakdown Dashboard

This API provides endpoints for:
1. Partner data visualization and analytics
2. Partner filtering and search
3. Partner performance metrics
4. CSV data management
"""

from flask import Flask, request, jsonify, Response
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
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from db_integration import db

# Load environment variables
load_dotenv()

# Set up Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI configuration from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
API_BASE_URL = os.getenv('API_BASE_URL')
OPENAI_MODEL_NAME = os.getenv('OPENAI_MODEL_NAME')

# Global variables for data
partner_data = None
csv_files_loaded = False

def load_csv_data():
    """Load partner data from CSV files"""
    global partner_data, csv_files_loaded
    
    try:
        csv_files = ['Quarter 1.csv', 'Quarter 2.csv', 'Quarter 3.csv']
        data_dir = '../data'
        all_data = []
        
        for csv_file in csv_files:
            file_path = os.path.join(data_dir, csv_file)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_data.append(df)
                logger.info(f"Loaded {csv_file} with {len(df)} records")
            else:
                logger.warning(f"CSV file not found: {file_path}")
        
        if all_data:
            partner_data = pd.concat(all_data, ignore_index=True)
            csv_files_loaded = True
            logger.info(f"Total partner records loaded: {len(partner_data)}")
            
            # Clean and standardize data
            standardize_data()
        else:
            error_msg = "No CSV files found in ../data directory. Required files: Quarter 1.csv, Quarter 2.csv, Quarter 3.csv"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
    except Exception as e:
        error_msg = f"Error loading CSV data: {str(e)}"
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
        try:
            gp_regions_mapping = db.get_partner_regions_mapping()
            if gp_regions_mapping:
                # Create a new column for GP regions
                partner_data['gp_region'] = partner_data['partner_id'].astype(str).map(gp_regions_mapping)
                # Replace the original region with GP region where available, keep original as fallback
                partner_data['region'] = partner_data['gp_region'].fillna(partner_data['region'])
                # Drop the temporary gp_region column
                partner_data.drop('gp_region', axis=1, inplace=True)
                logger.info(f"Applied GP region mapping to {len([v for v in gp_regions_mapping.values() if v])} partners")
            else:
                logger.warning("No GP region mapping retrieved from database, keeping original CSV regions")
        except Exception as e:
            logger.error(f"Error applying GP region mapping: {str(e)}, keeping original CSV regions")
        
        logger.info(f"Data standardization completed. {len(inactive_partners)} partners marked as Inactive (0 earnings)")
        
    except Exception as e:
        logger.error(f"Error standardizing data: {str(e)}")
        raise e

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

@app.route('/api/partner-overview', methods=['GET'])
def get_partner_overview():
    """Get partner overview statistics"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Get unique partners data (one record per partner) - use latest values to match list endpoint
        unique_partners = partner_data.groupby('partner_id').agg({
            'country': 'last',
            'partner_tier': 'last',
            'total_earnings': 'sum',
            'active_clients': 'last',
            'new_active_clients': 'sum',
            'total_deposits': 'sum',
            'is_app_dev': 'last'
        }).reset_index()
        
        # UPDATED: Separate active and inactive partners
        active_partners = unique_partners[unique_partners['partner_tier'] != 'Inactive']
        inactive_partners = unique_partners[unique_partners['partner_tier'] == 'Inactive']
        
        # Calculate top countries based on ACTIVE partners only (exclude Inactive from country counts)
        top_countries_series = active_partners['country'].value_counts().head(5)
        top_countries_dict = {}
        for country, count in top_countries_series.items():
            top_countries_dict[country] = int(count)
        
        # Calculate tier distribution including Inactive tier for visibility
        tier_counts = unique_partners['partner_tier'].value_counts()
        tier_order = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
        tier_distribution_dict = {}
        for tier in tier_order:
            if tier in tier_counts:
                tier_distribution_dict[tier] = int(tier_counts[tier])
        
        # Calculate metrics using ACTIVE partners only (exclude Inactive from totals)
        total_revenue = float(active_partners['total_earnings'].sum())
        total_deposits = float(active_partners['total_deposits'].sum())
        latest_active_clients = int(active_partners['active_clients'].sum())
        total_new_clients = int(active_partners['new_active_clients'].sum())
        api_developers = int(active_partners['is_app_dev'].sum())
        avg_earnings_per_partner = total_revenue / len(active_partners) if len(active_partners) > 0 else 0
        
        # Calculate overview metrics - using OrderedDict to preserve order
        # UPDATED: Show active partners count, excluding Inactive partners
        overview = OrderedDict([
            ('active_partners', len(active_partners)),  # Active partners only (excluding Inactive)
            ('total_partners', len(unique_partners)),   # Keep total for reference (including Inactive)
            ('total_revenue', total_revenue),           # From active partners only
            ('total_deposits', total_deposits),         # From active partners only
            ('total_active_clients', int(latest_active_clients)),
            ('total_new_clients', total_new_clients),
            ('avg_earnings_per_partner', float(avg_earnings_per_partner)),  # Based on active partners
            ('top_countries', top_countries_dict),      # Active partners only
            ('tier_distribution', tier_distribution_dict),  # Include Inactive for visibility
            ('api_developers', api_developers)
        ])
        
        return jsonify(overview)
        
    except Exception as e:
        logger.error(f"Error getting partner overview: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/partners', methods=['GET'])
def get_partners():
    """Get filtered partner list"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Get query parameters
        partner_id = request.args.get('partner_id')
        country = request.args.get('country')
        region = request.args.get('region')
        tier = request.args.get('tier')
        is_app_dev = request.args.get('is_app_dev')
        
        # Numerical filter parameters
        active_clients_min = request.args.get('active_clients_min', type=int)
        active_clients_max = request.args.get('active_clients_max', type=int)
        new_clients_min = request.args.get('new_clients_min', type=int)
        new_clients_max = request.args.get('new_clients_max', type=int)
        etr_filter = request.args.get('etr_filter')
        etr_min = request.args.get('etr_min', type=float)
        etr_max = request.args.get('etr_max', type=float)
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        sort_by = request.args.get('sort_by', 'total_earnings')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Apply non-tier filters first
        filtered_data = partner_data.copy()
        
        if partner_id:
            # Filter by partner ID(s) - support comma-separated values
            partner_ids = [pid.strip() for pid in partner_id.split(',') if pid.strip()]
            if partner_ids:
                filtered_data = filtered_data[filtered_data['partner_id'].astype(str).isin(partner_ids)]
        if country:
            filtered_data = filtered_data[filtered_data['country'] == country]
        if region:
            filtered_data = filtered_data[filtered_data['region'] == region]
        if is_app_dev:
            filtered_data = filtered_data[filtered_data['is_app_dev'] == (is_app_dev.lower() == 'true')]
        
        # Aggregate data by partner_id to show one row per partner (using latest values)
        partner_aggregated = filtered_data.groupby('partner_id').agg({
            # Static info - take latest occurrence (to match detail page)
            'first_name': 'last',
            'last_name': 'last', 
            'username': 'last',
            'country': 'last',
            'region': 'last',
            'partner_tier': 'last',  # Use latest tier to match detail page
            'is_app_dev': 'last',
            'joined_date': 'last',
            # Financial metrics - sum across all months (cumulative) + recent month data for EtR
            'total_earnings': 'sum',
            'company_revenue': 'sum',
            'total_deposits': 'sum',  # Cumulative total deposits
            # Recent month metrics for consistent display (like active_clients)
            'volume_usd': 'last',  # Recent month volume (not cumulative)
            'active_clients': 'last',
            'new_active_clients': 'last',  # Recent month new clients (not cumulative)
        }).reset_index()
        

        
        # Calculate months count for each partner
        months_count = filtered_data.groupby('partner_id').size().reset_index(name='months_count')
        partner_aggregated = partner_aggregated.merge(months_count, on='partner_id')
        
        # Calculate consistent monthly average (total_earnings / months_count)
        partner_aggregated['avg_monthly_earnings'] = partner_aggregated['total_earnings'] / partner_aggregated['months_count']
        
        # Keep the original CSV field for reference but use consistent calculation for display
        partner_aggregated['avg_past_3_months_earnings'] = partner_aggregated['avg_monthly_earnings']
        
        # Calculate Lifetime EtR ratio for sorting (before filtering)
        def calculate_lifetime_etr_for_sorting(row):
            earnings = row['total_earnings']  # Use lifetime total earnings
            revenue = row['company_revenue']  # Use lifetime total company revenue
            if revenue == 0:
                return 0
            ratio = (earnings / revenue) * 100
            # For sorting purposes, treat loss scenarios as negative values
            if revenue < 0 or earnings > revenue:
                return -abs(ratio)  # Make it negative for proper sorting
            return ratio
        
        partner_aggregated['etr_ratio'] = partner_aggregated.apply(calculate_lifetime_etr_for_sorting, axis=1)
        
        # Convert aggregated values to proper types
        for col in ['total_earnings', 'company_revenue', 'total_deposits', 'volume_usd', 'active_clients', 'new_active_clients', 'avg_monthly_earnings', 'avg_past_3_months_earnings', 'etr_ratio']:
            if col in partner_aggregated.columns:
                if col in ['active_clients', 'new_active_clients']:
                    partner_aggregated[col] = partner_aggregated[col].astype(int)
                else:
                    partner_aggregated[col] = partner_aggregated[col].astype(float)
        
        # Apply tier filter AFTER aggregation (filter by current/latest tier)
        if tier:
            partner_aggregated = partner_aggregated[partner_aggregated['partner_tier'] == tier]
        
        # Apply numerical filters AFTER aggregation
        if active_clients_min is not None:
            partner_aggregated = partner_aggregated[partner_aggregated['active_clients'] >= active_clients_min]
        if active_clients_max is not None:
            partner_aggregated = partner_aggregated[partner_aggregated['active_clients'] <= active_clients_max]
        if new_clients_min is not None:
            partner_aggregated = partner_aggregated[partner_aggregated['new_active_clients'] >= new_clients_min]
        if new_clients_max is not None:
            partner_aggregated = partner_aggregated[partner_aggregated['new_active_clients'] <= new_clients_max]
        
        # Apply EtR filter (using existing etr_ratio column based on lifetime data)
        if etr_filter:
            if etr_filter == 'double-loss':
                # Filter for double negative: lifetime revenue is negative (company lost money)
                partner_aggregated = partner_aggregated[partner_aggregated['company_revenue'] < 0]
            elif etr_filter == 'unprofitable':
                # Filter for single negative: lifetime earnings > positive lifetime revenue (unprofitable partner)
                unprofitable_condition = (
                    (partner_aggregated['company_revenue'] > 0) &
                    (partner_aggregated['total_earnings'] > partner_aggregated['company_revenue'])
                )
                partner_aggregated = partner_aggregated[unprofitable_condition]
            elif etr_filter == 'critically-low':
                partner_aggregated = partner_aggregated[
                    (partner_aggregated['etr_ratio'] >= 0.1) & (partner_aggregated['etr_ratio'] < 10)
                ]
            elif etr_filter == 'very-low':
                partner_aggregated = partner_aggregated[
                    (partner_aggregated['etr_ratio'] >= 10) & (partner_aggregated['etr_ratio'] < 20)
                ]
            elif etr_filter == 'low':
                partner_aggregated = partner_aggregated[
                    (partner_aggregated['etr_ratio'] >= 20) & (partner_aggregated['etr_ratio'] < 30)
                ]
            elif etr_filter == 'fair':
                partner_aggregated = partner_aggregated[
                    (partner_aggregated['etr_ratio'] >= 30) & (partner_aggregated['etr_ratio'] <= 40)
                ]
            elif etr_filter == 'high':
                partner_aggregated = partner_aggregated[partner_aggregated['etr_ratio'] > 40]
            elif etr_filter == 'custom':
                if etr_min is not None:
                    partner_aggregated = partner_aggregated[partner_aggregated['etr_ratio'] >= etr_min]
                if etr_max is not None:
                    partner_aggregated = partner_aggregated[partner_aggregated['etr_ratio'] <= etr_max]
        
        # Sort aggregated data
        if sort_by in partner_aggregated.columns:
            ascending = sort_order.lower() == 'asc'
            partner_aggregated = partner_aggregated.sort_values(by=sort_by, ascending=ascending)
        
        # Apply pagination
        total_count = len(partner_aggregated)
        paginated_data = partner_aggregated.iloc[offset:offset + limit]
        
        # Remove etr_ratio column before sending to frontend (frontend calculates it for display)
        if 'etr_ratio' in paginated_data.columns:
            paginated_data = paginated_data.drop('etr_ratio', axis=1)
        
        # Convert to JSON-serializable format
        result = {
            'partners': paginated_data.to_dict('records'),
            'total_count': total_count,
            'has_more': offset + limit < total_count
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting partners: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/partners/<partner_id>', methods=['GET'])
def get_partner_detail(partner_id):
    """Get detailed information for a specific partner"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400
        
        partner_records = partner_data[partner_data['partner_id'] == partner_id]
        
        if partner_records.empty:
            return jsonify({'error': 'Partner not found'}), 404
        
        # Get partner basic info (using latest record for static fields)
        latest_record = partner_records.iloc[-1]
        
        # Calculate aggregated totals across all months (convert to Python types)
        ytd_totals = {
            'total_earnings': float(partner_records['total_earnings'].sum()),
            'company_revenue': float(partner_records['company_revenue'].sum()),
            'total_deposits': float(partner_records['total_deposits'].sum()),
            'volume_usd': float(partner_records['volume_usd'].sum()),
            'total_active_clients': int(partner_records['active_clients'].iloc[-1]),  # Latest month's active clients
            'total_new_clients': int(partner_records['new_active_clients'].sum()),    # Sum of all new clients acquired
            'avg_monthly_earnings': float(partner_records['total_earnings'].mean()),
            'avg_monthly_revenue': float(partner_records['company_revenue'].mean()),
            'avg_monthly_deposits': float(partner_records['total_deposits'].mean()),
            'avg_monthly_volume': float(partner_records['volume_usd'].mean()),
            'avg_monthly_active_clients': float(partner_records['active_clients'].mean()),
            'avg_monthly_new_clients': float(partner_records['new_active_clients'].mean()),
            'months_count': int(len(partner_records))
        }
        
        # Get current month (latest) performance (convert to Python types)
        current_month = {
            'month': latest_record['month'].isoformat() if pd.notna(latest_record['month']) else None,
            'total_earnings': float(latest_record['total_earnings']),
            'company_revenue': float(latest_record['company_revenue']),
            'total_deposits': float(latest_record['total_deposits']),
            'volume_usd': float(latest_record['volume_usd']),
            'active_clients': int(latest_record['active_clients']),
            'new_active_clients': int(latest_record['new_active_clients'])
        }
        
        # Calculate monthly performance
        monthly_performance = partner_records.groupby('month').agg({
            'partner_tier': 'first',
            'total_earnings': 'first',
            'active_clients': 'first',
            'new_active_clients': 'first',
            'company_revenue': 'first',
            'total_deposits': 'first',
            'volume_usd': 'first'
        }).reset_index().sort_values('month', ascending=False).to_dict('records')
        
        # Combine basic info with totals
        partner_info = latest_record.to_dict()
        partner_info.update(ytd_totals)
        
        partner_detail = {
            'partner_info': partner_info,
            'current_month': current_month,
            'monthly_performance': monthly_performance,
            'total_records': len(partner_records)
        }
        
        return jsonify(partner_detail)
        
    except Exception as e:
        logger.error(f"Error getting partner detail: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/partners/<partner_id>/funnel', methods=['GET'])
def get_partner_funnel(partner_id):
    """Get monthly funnel performance data for a specific partner"""
    try:
        # Get funnel data from Supabase
        funnel_data = db.get_partner_funnel_data(partner_id)
        
        if not funnel_data:
            return jsonify({
                'funnel_data': [],
                'summary': {
                    'total_months': 0,
                    'total_demo': 0,
                    'total_real': 0,
                    'total_deposits': 0,
                    'total_trades': 0,
                    'avg_deposit_rate': 0.0,
                    'avg_trade_rate': 0.0
                }
            })
        
        # Calculate summary metrics based on new funnel structure
        total_demo = sum(month['demo_count'] for month in funnel_data)
        total_real = sum(month['real_count'] for month in funnel_data)
        total_deposits = sum(month['deposit_count'] for month in funnel_data)
        total_trades = sum(month['traded_count'] for month in funnel_data)
        
        avg_deposit_rate = (total_deposits / total_demo * 100) if total_demo > 0 else 0
        avg_trade_rate = (total_trades / total_demo * 100) if total_demo > 0 else 0
        
        # Get acquisition summary
        try:
            acquisition_data = db.get_partner_acquisition_summary(partner_id)
        except Exception as e:
            logger.warning(f"Could not fetch acquisition data for partner {partner_id}: {str(e)}")
            acquisition_data = {'acquisition_channels': [], 'total_channels': 0}
        
        return jsonify({
            'funnel_data': funnel_data,
            'summary': {
                'total_months': len(funnel_data),
                'total_demo': total_demo,
                'total_real': total_real,
                'total_deposits': total_deposits,
                'total_trades': total_trades,
                'avg_deposit_rate': round(avg_deposit_rate, 2),
                'avg_trade_rate': round(avg_trade_rate, 2),
                'recent_month': funnel_data[0] if funnel_data else None
            },
            'acquisition_data': acquisition_data
        })
        
    except Exception as e:
        logger.error(f"Error getting funnel data for partner {partner_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/tier-analytics', methods=['GET'])
def get_tier_analytics():
    """Get comprehensive tier-based analytics"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Get each partner's latest tier for consistent grouping
        partner_latest_tier = partner_data.groupby('partner_id')['partner_tier'].last().reset_index()
        partner_latest_tier.columns = ['partner_id', 'current_tier']
        
        # Merge current tier back to all monthly data for consistent grouping
        monthly_data_with_current_tier = partner_data.merge(partner_latest_tier, on='partner_id')
        
        # Get monthly data by current tier (not historical tier)
        # UPDATED: Only count partners who earned commission that month (total_earnings > 0)
        active_monthly_data = monthly_data_with_current_tier[monthly_data_with_current_tier['total_earnings'] > 0]
        
        monthly_tier_data = active_monthly_data.groupby(['month', 'current_tier']).agg({
            'partner_id': 'nunique',  # Unique partners per tier per month who earned commission
            'total_earnings': 'sum',  # Total earnings per tier per month
            'company_revenue': 'sum',  # Total company revenue per tier per month
            'total_deposits': 'sum',  # Total deposits per tier per month
            'active_clients': 'sum',  # Total active clients per tier per month
            'new_active_clients': 'sum'  # Total new clients per tier per month
        }).reset_index()
        
        # Rename for consistency
        monthly_tier_data = monthly_tier_data.rename(columns={'current_tier': 'partner_tier'})
        
        # Convert month to string for JSON serialization
        monthly_tier_data['month'] = monthly_tier_data['month'].dt.strftime('%Y-%m')
        
        # Get overall totals by tier (using latest tier per partner) - same logic as monthly
        unique_partners = partner_data.groupby('partner_id').agg({
            'partner_tier': 'last',
            'total_earnings': 'sum',
            'company_revenue': 'sum',
            'total_deposits': 'sum',
            'active_clients': 'last',
            'new_active_clients': 'sum'
        }).reset_index()
        
        tier_totals = unique_partners.groupby('partner_tier').agg({
            'partner_id': 'count',
            'total_earnings': 'sum',
            'company_revenue': 'sum',
            'total_deposits': 'sum',
            'active_clients': 'sum',
            'new_active_clients': 'sum'
        }).reset_index()
        
        # UPDATED: Separate active and inactive tiers for calculations
        active_tier_totals = tier_totals[tier_totals['partner_tier'] != 'Inactive']
        
        # Calculate proportions based on ACTIVE tiers only (exclude Inactive from percentage calculations)
        total_earnings = active_tier_totals['total_earnings'].sum()
        total_revenue = active_tier_totals['company_revenue'].sum()
        total_deposits = active_tier_totals['total_deposits'].sum()
        total_active_clients = active_tier_totals['active_clients'].sum()
        total_active_partners = active_tier_totals['partner_id'].sum()
        
        # Format tier totals with proportions
        tier_summary = []
        tier_order = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
        
        for tier in tier_order:
            tier_data = tier_totals[tier_totals['partner_tier'] == tier]
            if not tier_data.empty:
                row = tier_data.iloc[0]
                
                # UPDATED: Handle Inactive tier separately (show 0% for all percentages)
                if tier == 'Inactive':
                    tier_summary.append({
                        'tier': tier,
                        'partner_count': int(row['partner_id']),
                        'total_earnings': float(row['total_earnings']),
                        'total_revenue': float(row['company_revenue']),
                        'total_deposits': float(row['total_deposits']),
                        'active_clients': int(row['active_clients']),
                        'new_clients': int(row['new_active_clients']),
                        'earnings_percentage': 0.0,  # Always 0% for Inactive
                        'revenue_percentage': 0.0,   # Always 0% for Inactive
                        'deposits_percentage': 0.0,  # Always 0% for Inactive
                        'clients_percentage': 0.0,   # Always 0% for Inactive  
                        'partner_percentage': 0.0    # Always 0% for Inactive
                    })
                else:
                    tier_summary.append({
                        'tier': tier,
                        'partner_count': int(row['partner_id']),
                        'total_earnings': float(row['total_earnings']),
                        'total_revenue': float(row['company_revenue']),
                        'total_deposits': float(row['total_deposits']),
                        'active_clients': int(row['active_clients']),
                        'new_clients': int(row['new_active_clients']),
                        'earnings_percentage': float(row['total_earnings'] / total_earnings * 100) if total_earnings > 0 else 0,
                        'revenue_percentage': float(row['company_revenue'] / total_revenue * 100) if total_revenue > 0 else 0,
                        'deposits_percentage': float(row['total_deposits'] / total_deposits * 100) if total_deposits > 0 else 0,
                        'clients_percentage': float(row['active_clients'] / total_active_clients * 100) if total_active_clients > 0 else 0,
                        'partner_percentage': float(row['partner_id'] / total_active_partners * 100) if total_active_partners > 0 else 0
                    })
        
        # Format monthly data for charts (include all tiers including Inactive)
        months = sorted(monthly_tier_data['month'].unique())
        monthly_charts = {}
        
        for metric in ['total_earnings', 'company_revenue', 'total_deposits', 'partner_id', 'active_clients', 'new_active_clients']:
            monthly_charts[metric] = []
            for month in months:
                month_data = {'month': month}
                for tier in tier_order:
                    tier_month_data = monthly_tier_data[
                        (monthly_tier_data['month'] == month) & 
                        (monthly_tier_data['partner_tier'] == tier)
                    ]
                    if not tier_month_data.empty:
                        month_data[tier.lower()] = float(tier_month_data.iloc[0][metric])
                    else:
                        month_data[tier.lower()] = 0
                monthly_charts[metric].append(month_data)
        
        # UPDATED: Use total from all partners (including Inactive) for total count, but active totals for financial metrics
        total_all_partners = tier_totals['partner_id'].sum()
        
        analytics_data = {
            'tier_summary': tier_summary,
            'monthly_charts': monthly_charts,
            'totals': {
                'total_partners': int(total_all_partners),      # Include all partners
                'total_earnings': float(total_earnings),        # Active partners only
                'total_revenue': float(total_revenue),          # Active partners only
                'total_deposits': float(total_deposits),        # Active partners only
                'total_active_clients': int(total_active_clients)  # Active partners only
            }
        }
        
        return jsonify(analytics_data)
        
    except Exception as e:
        logger.error(f"Error getting tier analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai-insights', methods=['POST'])
def get_ai_insights():
    """Generate AI-powered insights based on context and data"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400
        
        request_data = request.get_json()
        context = request_data.get('context', 'dashboard')
        data = request_data.get('data', {})
        
        if context == 'dashboard':
            insights = generate_dashboard_insights(data)
        elif context == 'partner_detail':
            insights = generate_partner_insights(data)
        else:
            insights = {
                'summary': 'Invalid context provided',
                'key_findings': [],
                'recommendations': [],
                'trends': []
            }
        
        return jsonify(insights)
        
    except Exception as e:
        logger.error(f"Error generating AI insights: {str(e)}")
        return jsonify({'error': str(e)}), 500

def generate_dashboard_insights(data):
    """Generate AI-powered insights for the dashboard overview using LLM"""
    overview = data.get('overview', {})
    partners = data.get('partners', [])
    filters = data.get('activeFilters', {})
    
    insights = {
        'summary': '',
        'key_findings': [],
        'recommendations': [],
        'trends': []
    }
    
    try:
        # Check if LLM configuration is available
        if not all([OPENAI_API_KEY, API_BASE_URL, OPENAI_MODEL_NAME]):
            logger.error("Missing OpenAI configuration. Please check environment variables.")
            return {
                'summary': 'AI insights unavailable - missing API configuration',
                'key_findings': ['API configuration required for AI insights'],
                'recommendations': ['Please configure OPENAI_API_KEY, API_BASE_URL, and OPENAI_MODEL_NAME'],
                'trends': ['Contact system administrator for AI setup']
            }
        
        # Configure LLM
        llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=API_BASE_URL,
            model=OPENAI_MODEL_NAME,
            temperature=0.7
        )
        
        # Prepare comprehensive data summary for analysis
        total_partners = overview.get('total_partners', 0)
        total_revenue = overview.get('total_revenue', 0)
        avg_earnings = overview.get('avg_earnings_per_partner', 0)
        
        # Sample top performing partners for analysis
        top_partners = sorted(partners[:20], key=lambda x: x.get('total_earnings', 0), reverse=True) if partners else []
        
        # Get correct client metrics
        total_active_clients = overview.get('total_active_clients', 0)
        total_new_clients = overview.get('total_new_clients', 0)
        api_developers = overview.get('api_developers', 0)
        
        # Get actual count of API developers who are active as partners
        api_dev_partners_count = len(partner_data[partner_data['is_app_dev'] == True]['partner_id'].unique()) if partner_data is not None else 0
        api_dev_conversion_rate = (api_dev_partners_count/api_developers*100) if api_developers > 0 else 0
        
        # ENHANCED: Get comprehensive tier analytics data
        tier_analytics = {}
        try:
            # Calculate tier analytics (same logic as /api/tier-analytics endpoint)
            if partner_data is not None:
                # Get each partner's latest tier for consistent grouping
                partner_latest_tier = partner_data.groupby('partner_id')['partner_tier'].last().reset_index()
                partner_latest_tier.columns = ['partner_id', 'current_tier']
                
                # Get overall totals by tier (using latest tier per partner)
                unique_partners = partner_data.groupby('partner_id').agg({
                    'partner_tier': 'last',
                    'total_earnings': 'sum',
                    'company_revenue': 'sum',
                    'active_clients': 'last',
                    'new_active_clients': 'sum'
                }).reset_index()
                
                tier_totals = unique_partners.groupby('partner_tier').agg({
                    'partner_id': 'count',
                    'total_earnings': 'sum',
                    'company_revenue': 'sum', 
                    'active_clients': 'sum',
                    'new_active_clients': 'sum'
                }).reset_index()
                
                # Calculate proportions
                total_earnings_all = tier_totals['total_earnings'].sum()
                total_revenue_all = tier_totals['company_revenue'].sum()
                total_active_clients_all = tier_totals['active_clients'].sum()
                total_partners_all = tier_totals['partner_id'].sum()
                
                # Format tier analytics for AI analysis
                tier_summary = []
                tier_order = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
                
                for tier in tier_order:
                    tier_data = tier_totals[tier_totals['partner_tier'] == tier]
                    if not tier_data.empty:
                        row = tier_data.iloc[0]
                        tier_summary.append({
                            'tier': tier,
                            'partner_count': int(row['partner_id']),
                            'total_earnings': float(row['total_earnings']),
                            'total_revenue': float(row['company_revenue']),
                            'active_clients': int(row['active_clients']),
                            'earnings_percentage': float(row['total_earnings'] / total_earnings_all * 100) if total_earnings_all > 0 else 0,
                            'revenue_percentage': float(row['company_revenue'] / total_revenue_all * 100) if total_revenue_all > 0 else 0,
                            'clients_percentage': float(row['active_clients'] / total_active_clients_all * 100) if total_active_clients_all > 0 else 0,
                            'avg_earnings_per_partner': float(row['total_earnings'] / row['partner_id']) if row['partner_id'] > 0 else 0
                        })
                
                tier_analytics = {
                    'tier_summary': tier_summary,
                    'total_tiers': len(tier_summary)
                }
        except Exception as e:
            logger.warning(f"Could not calculate tier analytics: {str(e)}")
            tier_analytics = {'tier_summary': [], 'total_tiers': 0}
        
        data_summary = f"""
        PARTNER DASHBOARD ANALYSIS DATA:
        
        Overview Metrics:
        - Total Partners: {total_partners:,}
        - Total Revenue: ${total_revenue:,.2f}
        - Average Earnings per Partner: ${avg_earnings:,.2f}
        - Total Active Clients Across All Partners: {total_active_clients:,}
        - Total New Clients Acquired: {total_new_clients:,}
        - API Developers Total Registered: {api_developers:,}
        - API Developer Partners (Active as Partners): {api_dev_partners_count:,} out of {api_developers:,} total registered
        - API Developer Conversion Rate: {api_dev_conversion_rate:.1f}%
        
        Geographic Distribution & GP Regional Performance:
        - Top Countries: {overview.get('top_countries', {})}
        - Top 5 Countries Partner Count: {sum(overview.get('top_countries', {}).values())} ({sum(overview.get('top_countries', {}).values())/total_partners*100:.1f}% of total)
        - Geographic Concentration Risk: {'High' if sum(overview.get('top_countries', {}).values())/total_partners > 0.5 else 'Moderate' if sum(overview.get('top_countries', {}).values())/total_partners > 0.3 else 'Low'}
        
        Partner Performance Distribution:
        - Highest Earning Partner: ${max([p.get('total_earnings', 0) for p in partners]) if partners else 0:,.2f}
        - Lowest Earning Partner: ${min([p.get('total_earnings', 0) for p in partners]) if partners else 0:,.2f}
        - Partners Above Average: {len([p for p in partners if p.get('total_earnings', 0) > avg_earnings]) if partners else 0} out of {len(partners) if partners else 0} shown
        - API Developer Partners in Top Performers Sample: {len([p for p in partners if p.get('is_app_dev', False)]) if partners else 0} out of {len(partners) if partners else 0} shown
        
        Tier Analytics Summary (for context):
        - Partner Tier Distribution: {overview.get('tier_distribution', {})}
        {json.dumps(tier_analytics.get('tier_summary', []), indent=2) if len(tier_analytics.get('tier_summary', [])) > 0 else 'Tier analytics unavailable'}
        
        Sample Top Performing Partners:
        {json.dumps(top_partners[:10], indent=2) if top_partners else 'No partner data available'}
        
        Active Filters Applied: {filters}
        """
        
        system_prompt = """You are a senior business analyst specializing in partner affiliate programs and trading platforms. 

Analyze the partner dashboard data and provide strategic insights in exactly this JSON format:
{
    "summary": "Key insight 1 with specific numbers. Key insight 2 with actionable focus. Key insight 3 with critical concern.",
    "key_findings": ["Specific finding with numbers", "Critical issue requiring attention", "Opportunity with clear metrics"],
    "recommendations": ["Immediate action with clear steps", "Strategic improvement with timeline", "Risk mitigation with priority"],
    "trends": ["Pattern with data point", "Growth/decline trend with percentage"]
}

Requirements:
- Summary: Maximum 3 sentences, each under 25 words, include specific numbers
- Key findings: Maximum 3 items, focus on most critical insights across ALL dashboard areas
- Recommendations: Maximum 3 items, actionable with clear next steps
- Trends: Maximum 2 items, data-driven patterns only
- Include actual numbers and percentages from the data
- Prioritize urgent issues and high-impact opportunities across all metrics
- Be concise but specific
- BALANCED analysis covering: overall performance, geographic distribution, API developers, AND tier insights
- Only include tier insights if they reveal critical issues or high-impact opportunities
- Focus on the most actionable insights from the entire dashboard, not just one area
- Avoid over-emphasizing any single metric area unless it's the most critical business issue"""

        user_prompt = f"Analyze this partner dashboard data including comprehensive tier performance analytics and provide strategic business insights:\n\n{data_summary}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        
        # Try to parse JSON response
        try:
            ai_insights = json.loads(response.content)
            insights.update(ai_insights)
        except json.JSONDecodeError:
            # Fallback: parse structured text response
            content = response.content
            insights['summary'] = content.split('Summary:')[-1].split('Key Findings:')[0].strip() if 'Summary:' in content else content[:200]
            insights['key_findings'] = ['AI analysis completed', 'See summary for details']
            insights['recommendations'] = ['Review detailed analysis', 'Consider data-driven optimizations']
            insights['trends'] = ['Pattern analysis available', 'Monitor key performance indicators']
        
        logger.info("Successfully generated AI-powered dashboard insights with tier analytics")
        return insights
        
    except Exception as e:
        error_msg = f"Error generating AI insights: {str(e)}"
        logger.error(error_msg)
        
        # Provide helpful error messages
        if "401" in str(e) or "Authentication" in str(e):
            error_insight = "API authentication failed. Please verify your OpenAI API key and LiteLLM proxy configuration."
        elif "403" in str(e) or "Forbidden" in str(e):
            error_insight = "API access denied. Check your API permissions and usage limits."
        elif "Connection" in str(e) or "timeout" in str(e).lower():
            error_insight = "Cannot connect to AI service. Please check your API_BASE_URL and network connection."
        else:
            error_insight = f"AI service temporarily unavailable: {str(e)}"
        
        return {
            'summary': error_insight,
            'key_findings': ['AI insights temporarily unavailable'],
            'recommendations': ['Check system configuration', 'Contact administrator if issue persists'],
            'trends': ['Fallback to manual analysis', 'Retry after configuration fix']
        }

def generate_partner_insights(data):
    """Generate AI-powered insights for individual partner details using LLM"""
    partner_info = data.get('partner_info', {})
    monthly_perf = data.get('monthly_performance', [])
    current_month = data.get('current_month', {})
    
    insights = {
        'summary': '',
        'key_findings': [],
        'recommendations': [],
        'trends': []
    }
    
    try:
        # Check if LLM configuration is available
        if not all([OPENAI_API_KEY, API_BASE_URL, OPENAI_MODEL_NAME]):
            logger.error("Missing OpenAI configuration for partner insights.")
            return {
                'summary': 'AI insights unavailable - missing API configuration',
                'key_findings': ['API configuration required for AI insights'],
                'recommendations': ['Please configure OPENAI_API_KEY, API_BASE_URL, and OPENAI_MODEL_NAME'],
                'trends': ['Contact system administrator for AI setup']
            }
        
        # Configure LLM
        llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=API_BASE_URL,
            model=OPENAI_MODEL_NAME,
            temperature=0.7
        )
        
        # Calculate performance metrics
        total_earnings = partner_info.get('total_earnings', 0)
        partner_id = partner_info.get('partner_id', 'Unknown')
        tier = partner_info.get('partner_tier', 'Bronze')
        country = partner_info.get('country', 'Unknown')
        
        # Analyze monthly performance trends
        performance_analysis = ""
        tier_progression_analysis = ""
        
        if monthly_perf and len(monthly_perf) > 0:
            monthly_earnings = [m.get('total_earnings', 0) for m in monthly_perf]
            avg_monthly = sum(monthly_earnings) / len(monthly_earnings)
            max_month = max(monthly_earnings)
            min_month = min(monthly_earnings)
            
            # Growth trend analysis
            if len(monthly_earnings) >= 3:
                recent_avg = sum(monthly_earnings[-3:]) / 3
                earlier_avg = sum(monthly_earnings[:-3]) / len(monthly_earnings[:-3]) if len(monthly_earnings) > 3 else avg_monthly
                growth_rate = ((recent_avg - earlier_avg) / earlier_avg * 100) if earlier_avg > 0 else 0
                
                performance_analysis = f"""
                Monthly Performance Analysis:
                - Average Monthly Earnings: ${avg_monthly:,.2f}
                - Best Month: ${max_month:,.2f}
                - Lowest Month: ${min_month:,.2f}
                - Recent 3-Month Trend: {growth_rate:+.1f}% growth
                - Performance Consistency: {(1 - (max_month - min_month) / avg_monthly) * 100:.1f}% consistency score
                """
            
            # ENHANCED: Tier progression analysis
            tier_history = []
            tier_changes = []
            
            # Sort monthly performance by date to ensure correct chronological order
            sorted_monthly_perf = sorted(monthly_perf, key=lambda x: x.get('month', ''), reverse=False)
            
            for i, month_data in enumerate(sorted_monthly_perf):
                month_tier = month_data.get('partner_tier', 'Bronze')
                month_date = month_data.get('month', '')
                month_active_clients = month_data.get('active_clients', 0)
                month_new_clients = month_data.get('new_active_clients', 0)
                tier_history.append({
                    'month': month_date, 
                    'tier': month_tier,
                    'active_clients': month_active_clients,
                    'new_clients': month_new_clients
                })
                
                if i > 0:
                    prev_tier = sorted_monthly_perf[i-1].get('partner_tier', 'Bronze')
                    if prev_tier != month_tier:
                        tier_changes.append({
                            'from_tier': prev_tier,
                            'to_tier': month_tier,
                            'month': month_date,
                            'direction': 'upgrade' if get_tier_rank(month_tier) > get_tier_rank(prev_tier) else 'downgrade'
                        })
            
            # Calculate tier stability and progression metrics
            unique_tiers = list(set([t['tier'] for t in tier_history]))
            tier_stability = len(unique_tiers)
            current_tier = tier_history[-1]['tier'] if tier_history else 'Bronze'
            first_tier = tier_history[0]['tier'] if tier_history else 'Bronze'
            
            # Calculate client acquisition trends
            client_trend_analysis = ""
            if len(tier_history) >= 3:
                recent_clients = [t['active_clients'] for t in tier_history[-3:]]
                earlier_clients = [t['active_clients'] for t in tier_history[:-3]]
                recent_new_clients = [t['new_clients'] for t in tier_history[-3:]]
                
                avg_recent_active = sum(recent_clients) / len(recent_clients)
                avg_earlier_active = sum(earlier_clients) / len(earlier_clients) if earlier_clients else avg_recent_active
                total_recent_new = sum(recent_new_clients)
                
                client_growth_rate = ((avg_recent_active - avg_earlier_active) / avg_earlier_active * 100) if avg_earlier_active > 0 else 0
                
                client_trend_analysis = f"""
                Client Acquisition Trend Analysis:
                - Recent 3-month Active Clients Average: {avg_recent_active:.0f}
                - Earlier Period Active Clients Average: {avg_earlier_active:.0f}
                - Active Clients Trend: {client_growth_rate:+.1f}% change
                - Recent 3-month New Clients Total: {total_recent_new}
                - Client Acquisition Momentum: {'Strong' if total_recent_new > 100 else 'Moderate' if total_recent_new > 20 else 'Weak'}
                """
            
            tier_progression_analysis = f"""
            Tier Progression Analysis:
            - Overall Journey: {first_tier} → {current_tier} ({get_tier_progression_status(first_tier, current_tier)})
            - Current Tier: {current_tier}
            - Starting Tier: {first_tier} 
            - Tier Changes: {len(tier_changes)} changes over {len(sorted_monthly_perf)} months
            - Tier Stability: {tier_stability} different tiers experienced
            - Recent Tier Changes: {json.dumps(tier_changes[-3:], indent=2) if tier_changes else 'No recent tier changes'}
            - Complete Tier & Client History: {json.dumps(tier_history, indent=2)}
            {client_trend_analysis}
            """
        
        # Get client metrics
        total_active_clients = partner_info.get('total_active_clients', 0)
        total_new_clients = partner_info.get('total_new_clients', 0)
        avg_monthly_active_clients = partner_info.get('avg_monthly_active_clients', 0)
        avg_monthly_new_clients = partner_info.get('avg_monthly_new_clients', 0)
        current_month_active_clients = current_month.get('active_clients', 0)
        current_month_new_clients = current_month.get('new_active_clients', 0)
        
        # Calculate client growth trend safely
        if avg_monthly_active_clients > 0:
            growth_pct = ((current_month_active_clients - avg_monthly_active_clients) / avg_monthly_active_clients * 100)
            client_growth_trend = f"{growth_pct:+.1f}% vs monthly average"
        else:
            client_growth_trend = "N/A (no historical data)"
        
        # Prepare comprehensive partner data for analysis
        data_summary = f"""
        INDIVIDUAL PARTNER ANALYSIS DATA:
        
        Partner Information:
        - Partner ID: {partner_id}
        - Country: {country}
        - Current Tier: {tier}
        - API Developer Status: {partner_info.get('is_app_dev', False)}
        - Join Date: {partner_info.get('joined_date', 'Unknown')}
        
        PRIMARY FOCUS - CLIENT ACQUISITION METRICS:
        - Current Active Clients: {total_active_clients:,} (latest month)
        - Average Monthly Active Clients: {avg_monthly_active_clients:.1f}
        - Total New Clients Acquired: {total_new_clients:,} (lifetime)
        - Average Monthly New Clients: {avg_monthly_new_clients:.1f}
        - Current Month Active Clients: {current_month_active_clients:,}
        - Current Month New Clients: {current_month_new_clients:,}
        - Client Growth Trend: {client_growth_trend}
        
        FINANCIAL PERFORMANCE CONTEXT:
        - Total Lifetime Earnings: ${total_earnings:,.2f}
        - Current Month Earnings: ${current_month.get('total_earnings', 0):,.2f}
        - Average Monthly Earnings: ${partner_info.get('avg_monthly_earnings', 0):,.2f}
        - Earnings per Active Client Ratio: ${(current_month.get('total_earnings', 0) / current_month_active_clients) if current_month_active_clients > 0 else 0:,.2f} per client
        - Company Revenue (Current Month): ${current_month.get('company_revenue', 0):,.2f}
        
        {performance_analysis}
        {tier_progression_analysis}
        
        Monthly Performance History (Focus on Client Metrics):
        {json.dumps(monthly_perf[-12:], indent=2) if monthly_perf else 'No monthly performance data available'}
        
        Current Month Performance:
        {json.dumps(current_month, indent=2) if current_month else 'No current month data available'}
        
        Partner Engagement Indicators:
        - Has Active Clients: {total_active_clients > 0}
        - Client Acquisition Performance: {'High' if total_active_clients > avg_monthly_active_clients else 'Moderate' if total_active_clients > 0 else 'Low'}
        - Recent Client Activity: {bool(current_month_new_clients > 0) if current_month else False}
        - Technical Integration: {partner_info.get('is_app_dev', False)}
        """
        
        system_prompt = """You are a senior partner success manager specializing in affiliate marketing and trading platforms.

Analyze this individual partner's data and provide strategic insights in exactly this JSON format:
{
    "summary": "Key client acquisition insight with numbers. Tier progression status with timeline. Critical action needed (client or earnings focus).",
    "key_findings": ["Client acquisition pattern with data", "Tier progression analysis", "Performance opportunity or risk (client/earnings)"],
    "recommendations": ["Immediate action with timeline (client/earnings focus)", "Client retention or revenue improvement step", "Tier advancement strategy with specific targets"],
    "trends": ["Client acquisition monthly pattern with numbers", "Tier progression timeline with performance correlation"]
}

Requirements:
- Summary: Maximum 3 sentences, focus on MOST CRITICAL METRICS (clients or earnings), then tier progression
- Key findings: Maximum 3 items, prioritize the most actionable insights from client acquisition, retention, and earnings
- Recommendations: Maximum 3 items, focus on strategies with highest impact (client growth, earnings optimization, or tier advancement)
- Trends: Maximum 2 items, emphasize patterns that drive business outcomes
- BALANCED APPROACH: Primarily focus on client metrics, but include 1-2 lines about earnings when insightful or actionable
- Include earnings insights when: revenue trends correlate with client patterns, earnings per client ratios reveal opportunities, or revenue optimization could accelerate tier advancement
- Analyze tier progression correctly from earliest to latest month
- Identify key performance drivers for tier changes (client acquisition, retention, or revenue efficiency)
- Provide actionable recommendations with specific targets for maximum business impact
- Be concise but strategic with measurable goals"""

        user_prompt = f"Analyze this partner's performance data and provide strategic insights:\n\n{data_summary}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        
        # Try to parse JSON response
        try:
            ai_insights = json.loads(response.content)
            insights.update(ai_insights)
        except json.JSONDecodeError:
            # Fallback: parse structured text response
            content = response.content
            insights['summary'] = content.split('Summary:')[-1].split('Key Findings:')[0].strip() if 'Summary:' in content else content[:200]
            insights['key_findings'] = ['AI analysis completed', 'See summary for detailed analysis']
            insights['recommendations'] = ['Review performance trends', 'Focus on client acquisition']
            insights['trends'] = ['Monitor monthly performance', 'Track tier advancement progress']
        
        logger.info(f"Successfully generated AI-powered insights for partner {partner_id}")
        return insights
        
    except Exception as e:
        error_msg = f"Error generating AI insights for partner: {str(e)}"
        logger.error(error_msg)
        
        # Provide helpful error messages
        if "401" in str(e) or "Authentication" in str(e):
            error_insight = "API authentication failed. Please verify your OpenAI API key and LiteLLM proxy configuration."
        elif "403" in str(e) or "Forbidden" in str(e):
            error_insight = "API access denied. Check your API permissions and usage limits."
        elif "Connection" in str(e) or "timeout" in str(e).lower():
            error_insight = "Cannot connect to AI service. Please check your API_BASE_URL and network connection."
        else:
            error_insight = f"AI service temporarily unavailable: {str(e)}"
        
        return {
            'summary': error_insight,
            'key_findings': ['AI insights temporarily unavailable'],
            'recommendations': ['Check system configuration', 'Contact administrator if issue persists'],
            'trends': ['Fallback to manual analysis', 'Retry after configuration fix']
        }

# Helper functions for AI insights
def get_tier_rank(tier):
    """Assign a rank to a partner tier for progression analysis."""
    tier_ranks = {
        'Platinum': 4,
        'Gold': 3,
        'Silver': 2,
        'Bronze': 1,
        'Inactive': 0  # Inactive is the lowest tier
    }
    return tier_ranks.get(tier, 0) # Default to 0 if tier not found

def get_tier_progression_status(start_tier, end_tier):
    """Determine the overall progression status based on start and end tiers."""
    start_rank = get_tier_rank(start_tier)
    end_rank = get_tier_rank(end_tier)
    
    if start_rank == 0 or end_rank == 0:
        return "Tier progression analysis unavailable"
        
    if end_rank > start_rank:
        return f"Tier advanced from {start_tier} to {end_tier} (upgrade)"
    elif end_rank < start_rank:
        return f"Tier degraded from {start_tier} to {end_tier} (downgrade)"
    else:
        return "Tier remained the same"

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