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
from region_mapping import REGION_COUNTRY_MAPPING, get_countries_for_region, get_all_regions

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
        # Try both relative paths depending on where the script is run from
        possible_data_dirs = ['../data', './data', '/Users/manaskarra/Desktop/Work/PDash/data']
        data_dir = None
        
        for dir_path in possible_data_dirs:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                data_dir = dir_path
                break
        
        if not data_dir:
            raise FileNotFoundError(f"Data directory not found. Tried: {possible_data_dirs}")
        
        logger.info(f"Using data directory: {data_dir}")
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
            error_msg = f"No CSV files found in {data_dir} directory. Required files: Quarter 1.csv, Quarter 2.csv, Quarter 3.csv"
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
        
        # Get additional partner information from database (including date_joined for age calculation)
        try:
            partner_db_info = db.get_partner_info_details(partner_id)
            if partner_db_info:
                # Calculate partner age if date_joined is available
                if partner_db_info.get('date_joined'):
                    from datetime import datetime
                    
                    # Parse the date_joined string back to datetime for calculation
                    date_joined = datetime.fromisoformat(partner_db_info['date_joined'].replace('Z', '+00:00'))
                    current_date = datetime.now(date_joined.tzinfo) if date_joined.tzinfo else datetime.now()
                    
                    # Calculate age in days
                    age_days = (current_date - date_joined).days
                    
                    # Calculate age components
                    years = age_days // 365
                    remaining_days = age_days % 365
                    months = remaining_days // 30
                    days = remaining_days % 30
                    
                    # Create age badge based on tenure
                    if age_days >= 1825:  # 5+ years
                        age_badge = 'age-5yr-plus'
                        age_milestone = '5+ Years'
                    elif age_days >= 1460:  # 4+ years  
                        age_badge = 'age-4yr'
                        age_milestone = '4+ Years'
                    elif age_days >= 1095:  # 3+ years
                        age_badge = 'age-3yr'
                        age_milestone = '3+ Years'
                    elif age_days >= 730:   # 2+ years
                        age_badge = 'age-2yr'
                        age_milestone = '2+ Years'
                    elif age_days >= 548:   # 18+ months
                        age_badge = 'age-18mo'
                        age_milestone = '18+ Months'
                    elif age_days >= 365:   # 1+ year
                        age_badge = 'age-1yr'
                        age_milestone = '1+ Year'
                    elif age_days >= 180:   # 6+ months
                        age_badge = 'age-6mo'
                        age_milestone = '6+ Months'
                    elif age_days >= 90:    # 3+ months
                        age_badge = 'age-3mo'
                        age_milestone = '3+ Months'
                    elif age_days >= 30:    # 1+ month
                        age_badge = 'age-1mo'
                        age_milestone = '1+ Month'
                    else:
                        age_badge = 'new'
                        age_milestone = 'New Partner'
                    
                    # Create readable age string
                    if years > 0:
                        if months > 0:
                            age_display = f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
                        else:
                            age_display = f"{years} year{'s' if years != 1 else ''}"
                    elif months > 0:
                        if days > 0:
                            age_display = f"{months} month{'s' if months != 1 else ''}, {days} day{'s' if days != 1 else ''}"
                        else:
                            age_display = f"{months} month{'s' if months != 1 else ''}"
                    else:
                        age_display = f"{age_days} day{'s' if age_days != 1 else ''}"
                    
                    # Add age information to partner_info
                    partner_info.update({
                        'date_joined': partner_db_info['date_joined'],
                        'partner_age_days': age_days,
                        'partner_age_display': age_display,
                        'partner_age_badge': age_badge,
                        'partner_age_milestone': age_milestone
                    })
                
                # Add other useful fields from partner_info table
                useful_fields = [
                    'partner_status', 'partner_level', 'aff_type', 'activation_phase',
                    'is_master_plan', 'is_revshare_plan', 'is_turnover_plan', 'is_cpa_plan', 'is_ib_plan',
                    'parent_partner_id', 'subaff_count', 'first_client_joined_date', 'first_client_deposit_date',
                    'first_client_trade_date', 'first_earning_date', 'last_client_joined_date', 'last_earning_date',
                    'webinar_count', 'seminar_count', 'sponsorship_event_count', 'conference_count', 'attended_onboarding_event'
                ]
                
                for field in useful_fields:
                    if field in partner_db_info and partner_db_info[field] is not None:
                        partner_info[field] = partner_db_info[field]
                        
        except Exception as e:
            logger.warning(f"Could not fetch additional partner info for {partner_id}: {str(e)}")
            # Continue without the additional info
        
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

@app.route('/api/partner-application-countries', methods=['GET'])
def get_partner_application_countries():
    """Get list of all countries available for partner application funnel filtering"""
    try:
        countries = db.get_partner_application_countries()
        return jsonify({
            'countries': countries,
            'total_countries': len(countries)
        })
        
    except Exception as e:
        logger.error(f"Error getting partner application countries: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/partner-application-funnel', methods=['GET'])
def get_partner_application_funnel():
    """Get partner application funnel analytics including monthly trends, activation metrics, and distribution data"""
    try:
        # Get optional filter parameters
        selected_month = request.args.get('month', 'all')
        countries_param = request.args.get('countries', '')
        
        # Parse countries parameter (comma-separated values)
        selected_countries = []
        if countries_param and countries_param.strip():
            selected_countries = [country.strip() for country in countries_param.split(',') if country.strip()]
        
        # Get application funnel data from Supabase with filters
        funnel_data = db.get_partner_application_funnel_data(selected_month, selected_countries)
        
        if not funnel_data:
            return jsonify({
                'monthly_data': [],
                'country_distribution': [],
                'region_distribution': [],
                'summary': {},
                'error': 'No application funnel data available'
            })
        
        return jsonify({
            'monthly_data': funnel_data.get('monthly_data', []),
            'country_distribution': funnel_data.get('country_distribution', []),
            'region_distribution': funnel_data.get('region_distribution', []),
            'summary': funnel_data.get('summary', {}),
            'total_months': len(funnel_data.get('monthly_data', [])),
            'total_countries': len(funnel_data.get('country_distribution', [])),
            'total_regions': len(funnel_data.get('region_distribution', []))
        })
        
    except Exception as e:
        logger.error(f"Error getting partner application funnel data: {str(e)}")
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

@app.route('/api/country-tier-analytics', methods=['GET'])
def get_country_tier_analytics():
    """Get comprehensive tier analytics for a specific country or region using CSV data for countries and Supabase data for regions"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400
        
        country = request.args.get('country')
        region = request.args.get('region')
        
        # Handle URL encoding where + should become spaces
        if region:
            region = region.replace('+', ' ')
        if country:
            country = country.replace('+', ' ')
        
        if not country and not region:
            return jsonify({'error': 'Either country or region parameter is required'}), 400
        
        # For regions, use hardcoded mapping to get countries in that region
        if region:
            # Get countries that belong to this region from hardcoded mapping
            region_countries = get_countries_for_region(region)
            
            if not region_countries:
                return jsonify({
                    'success': True,
                    'data': {
                        'summary': {},
                        'monthly_tier_data': {},
                        'country_rankings': {},
                        'available_months': []
                    },
                    'country': country,
                    'region': region
                })
            
            # Filter CSV data by countries in this region
            filtered_data = partner_data[partner_data['country'].isin(region_countries)].copy()
        else:
            # Filter CSV data by country
            filtered_data = partner_data[partner_data['country'] == country].copy()
        
        if filtered_data.empty:
            return jsonify({
                'success': True,
                'data': {
                    'summary': {},
                    'monthly_tier_data': {},
                    'country_rankings': {},
                    'available_months': []
                },
                'country': country,
                'region': region
            })
        
        # Get each partner's latest tier for consistent grouping
        partner_latest_tier = filtered_data.groupby('partner_id')['partner_tier'].last().reset_index()
        partner_latest_tier.columns = ['partner_id', 'current_tier']
        
        # Merge current tier back to all monthly data for consistent grouping
        monthly_data_with_current_tier = filtered_data.merge(partner_latest_tier, on='partner_id')
        
        # Get monthly data by current tier
        monthly_tier_data = monthly_data_with_current_tier.groupby(['month', 'current_tier']).agg({
            'partner_id': 'nunique',
            'total_earnings': 'sum',
            'company_revenue': 'sum',
            'total_deposits': 'sum',
            'active_clients': 'sum',
            'new_active_clients': 'sum',
            'volume_usd': 'sum'
        }).reset_index()
        
        # Rename for consistency
        monthly_tier_data = monthly_tier_data.rename(columns={'current_tier': 'partner_tier'})
        
        # Sort by month descending first (latest to earliest) and keep original date for sorting
        monthly_tier_data = monthly_tier_data.sort_values('month', ascending=False)
        
        # Create a month sorting reference before converting to string
        month_order = monthly_tier_data['month'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
        month_order_list = [period.strftime('%b %Y') for period in month_order]
        
        # Convert month to string for JSON serialization
        monthly_tier_data['month'] = monthly_tier_data['month'].dt.strftime('%b %Y')
        
        # Get overall totals by tier
        unique_partners = filtered_data.groupby('partner_id').agg({
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
        
        # Calculate overall summary
        total_partners = tier_totals['partner_id'].sum()
        # Calculate active partners (excluding Inactive tier)
        active_tier_totals = tier_totals[tier_totals['partner_tier'] != 'Inactive']
        total_active_partners = active_tier_totals['partner_id'].sum()
        total_earnings = tier_totals['total_earnings'].sum()
        total_company_revenue = tier_totals['company_revenue'].sum()
        total_deposits = tier_totals['total_deposits'].sum()
        total_clients = tier_totals['active_clients'].sum()
        
        # Format monthly tier data for frontend (preserve chronological order)
        from collections import OrderedDict
        monthly_data = OrderedDict()
        
        # Process in chronological order (latest first)
        for month_str in month_order_list:
            monthly_data[month_str] = {}
        
        # Fill in the tier data (initially without rankings)
        for _, row in monthly_tier_data.iterrows():
            month_str = row['month']
            tier = row['partner_tier']
            monthly_data[month_str][tier] = {
                'count': int(row['partner_id']),
                'earnings': float(row['total_earnings']),
                'revenue': float(row['company_revenue']),
                'deposits': float(row['total_deposits']),
                'active_clients': int(row['active_clients']),
                'new_clients': int(row['new_active_clients']),
                'volume': float(row['volume_usd'])
            }
        
        # Calculate real rankings by comparing against all countries OR all regions
        if region:
            # For regions, calculate rankings against all regions
            try:
                # Use hardcoded region to country mapping
                region_country_mapping = REGION_COUNTRY_MAPPING
                
                # Calculate metrics for each region by aggregating its countries' data
                all_regions_data = []
                for region_name, countries in region_country_mapping.items():
                    region_data = partner_data[partner_data['country'].isin(countries)]
                    if not region_data.empty:
                        # Calculate active partners for this region (excluding Inactive tier)
                        region_partner_tiers = region_data.groupby('partner_id')['partner_tier'].last().reset_index()
                        active_partners_count = len(region_partner_tiers[region_partner_tiers['partner_tier'] != 'Inactive'])
                        
                        # Aggregate region metrics
                        region_totals = region_data.groupby('partner_id').agg({
                            'total_earnings': 'sum',
                            'company_revenue': 'sum',
                            'total_deposits': 'sum',
                            'active_clients': 'last',
                            'new_active_clients': 'sum'
                        }).sum()
                        
                        all_regions_data.append({
                            'region': region_name,
                            'partner_id': len(region_data['partner_id'].unique()),
                            'active_partners': active_partners_count,
                            'total_earnings': region_totals['total_earnings'],
                            'company_revenue': region_totals['company_revenue'],
                            'total_deposits': region_totals['total_deposits'],
                            'active_clients': region_totals['active_clients'],
                            'new_active_clients': region_totals['new_active_clients']
                        })
                
                all_regions_df = pd.DataFrame(all_regions_data)
                
                # Calculate ETR and ETD ratios for each region
                all_regions_df['etr_ratio'] = np.where(
                    all_regions_df['company_revenue'] > 0,
                    (all_regions_df['total_earnings'] / all_regions_df['company_revenue']) * 100,
                    0
                )
                all_regions_df['etd_ratio'] = np.where(
                    all_regions_df['total_deposits'] > 0,
                    (all_regions_df['total_earnings'] / all_regions_df['total_deposits']) * 100,
                    0
                )
                
                # Calculate rankings for regions
                all_regions_df['earnings_rank'] = all_regions_df['total_earnings'].rank(method='dense', ascending=False)
                all_regions_df['revenue_rank'] = all_regions_df['company_revenue'].rank(method='dense', ascending=False)
                all_regions_df['deposits_rank'] = all_regions_df['total_deposits'].rank(method='dense', ascending=False)
                all_regions_df['clients_rank'] = all_regions_df['active_clients'].rank(method='dense', ascending=False)
                all_regions_df['partners_rank'] = all_regions_df['partner_id'].rank(method='dense', ascending=False)
                all_regions_df['active_partners_rank'] = all_regions_df['active_partners'].rank(method='dense', ascending=False)
                all_regions_df['etr_rank'] = all_regions_df['etr_ratio'].rank(method='dense', ascending=False)
                all_regions_df['etd_rank'] = all_regions_df['etd_ratio'].rank(method='dense', ascending=False)
                
                # Calculate monthly averages for ranking
                month_count = len(month_order_list) if month_order_list else 1
                all_regions_df['avg_monthly_revenue'] = all_regions_df['company_revenue'] / month_count
                all_regions_df['avg_monthly_earnings'] = all_regions_df['total_earnings'] / month_count
                all_regions_df['avg_monthly_deposits'] = all_regions_df['total_deposits'] / month_count
                all_regions_df['avg_monthly_new_clients'] = all_regions_df['new_active_clients'] / month_count
                
                # Calculate monthly average rankings for regions
                all_regions_df['avg_monthly_revenue_rank'] = all_regions_df['avg_monthly_revenue'].rank(method='dense', ascending=False)
                all_regions_df['avg_monthly_earnings_rank'] = all_regions_df['avg_monthly_earnings'].rank(method='dense', ascending=False)
                all_regions_df['avg_monthly_deposits_rank'] = all_regions_df['avg_monthly_deposits'].rank(method='dense', ascending=False)
                all_regions_df['avg_monthly_new_clients_rank'] = all_regions_df['avg_monthly_new_clients'].rank(method='dense', ascending=False)
                
                # Get rankings for the current region
                current_region_data = all_regions_df[all_regions_df['region'] == region]
                ranking_data_df = all_regions_df
                current_data = current_region_data
                
            except Exception as e:
                logger.error(f"Error calculating region rankings: {str(e)}")
                # Fallback to default rankings
                earnings_rank = revenue_rank = deposits_rank = clients_rank = partners_rank = active_partners_rank = etr_rank = etd_rank = 1
                avg_monthly_revenue_rank = avg_monthly_earnings_rank = avg_monthly_deposits_rank = avg_monthly_new_clients_rank = 1
        else:
            # For countries, calculate rankings against all countries (existing logic)
            all_countries_data = partner_data.groupby('country').agg({
                'partner_id': 'nunique',
                'total_earnings': 'sum',
                'company_revenue': 'sum',
                'total_deposits': 'sum',
                'active_clients': 'sum'
            }).reset_index()
            
            # Calculate active partners for each country (excluding Inactive tier)
            active_partners_by_country = []
            for country_name in partner_data['country'].unique():
                if pd.isna(country_name):
                    continue
                country_data = partner_data[partner_data['country'] == country_name]
                country_partner_tiers = country_data.groupby('partner_id')['partner_tier'].last().reset_index()
                active_partners_count = len(country_partner_tiers[country_partner_tiers['partner_tier'] != 'Inactive'])
                active_partners_by_country.append({
                    'country': country_name,
                    'active_partners': active_partners_count
                })
            
            active_partners_df = pd.DataFrame(active_partners_by_country)
            all_countries_data = all_countries_data.merge(active_partners_df, on='country', how='left')
            all_countries_data['active_partners'] = all_countries_data['active_partners'].fillna(0)
            
            # Calculate ETR and ETD ratios for each country
            all_countries_data['etr_ratio'] = np.where(
                all_countries_data['company_revenue'] > 0,
                (all_countries_data['total_earnings'] / all_countries_data['company_revenue']) * 100,
                0
            )
            all_countries_data['etd_ratio'] = np.where(
                all_countries_data['total_deposits'] > 0,
                (all_countries_data['total_earnings'] / all_countries_data['total_deposits']) * 100,
                0
            )
            
            # Calculate rankings
            all_countries_data['earnings_rank'] = all_countries_data['total_earnings'].rank(method='dense', ascending=False)
            all_countries_data['revenue_rank'] = all_countries_data['company_revenue'].rank(method='dense', ascending=False)
            all_countries_data['deposits_rank'] = all_countries_data['total_deposits'].rank(method='dense', ascending=False)
            all_countries_data['clients_rank'] = all_countries_data['active_clients'].rank(method='dense', ascending=False)
            all_countries_data['partners_rank'] = all_countries_data['partner_id'].rank(method='dense', ascending=False)
            all_countries_data['active_partners_rank'] = all_countries_data['active_partners'].rank(method='dense', ascending=False)
            all_countries_data['etr_rank'] = all_countries_data['etr_ratio'].rank(method='dense', ascending=False)
            all_countries_data['etd_rank'] = all_countries_data['etd_ratio'].rank(method='dense', ascending=False)
            
            # Calculate monthly averages for ranking
            month_count = len(month_order_list) if month_order_list else 1
            all_countries_data['avg_monthly_revenue'] = all_countries_data['company_revenue'] / month_count
            all_countries_data['avg_monthly_earnings'] = all_countries_data['total_earnings'] / month_count
            all_countries_data['avg_monthly_deposits'] = all_countries_data['total_deposits'] / month_count
            
            # Calculate new active clients by month for each country (sum all monthly new clients)
            monthly_new_clients_by_country = partner_data.groupby(['country', 'month'])['new_active_clients'].sum().reset_index()
            total_new_clients_by_country = monthly_new_clients_by_country.groupby('country')['new_active_clients'].sum().reset_index()
            all_countries_data = all_countries_data.merge(total_new_clients_by_country, on='country', how='left')
            all_countries_data['new_active_clients'] = all_countries_data['new_active_clients'].fillna(0)
            all_countries_data['avg_monthly_new_clients'] = all_countries_data['new_active_clients'] / month_count
            
            # Calculate monthly average rankings
            all_countries_data['avg_monthly_revenue_rank'] = all_countries_data['avg_monthly_revenue'].rank(method='dense', ascending=False)
            all_countries_data['avg_monthly_earnings_rank'] = all_countries_data['avg_monthly_earnings'].rank(method='dense', ascending=False)
            all_countries_data['avg_monthly_deposits_rank'] = all_countries_data['avg_monthly_deposits'].rank(method='dense', ascending=False)
            all_countries_data['avg_monthly_new_clients_rank'] = all_countries_data['avg_monthly_new_clients'].rank(method='dense', ascending=False)
            
            # Get rankings for the current country
            current_country_data = all_countries_data[all_countries_data['country'] == country]
            ranking_data_df = all_countries_data
            current_data = current_country_data
        
        # Extract rankings from the appropriate dataset (regions or countries)
        if region and 'current_data' in locals() and not current_data.empty:
            earnings_rank = int(current_data.iloc[0]['earnings_rank'])
            revenue_rank = int(current_data.iloc[0]['revenue_rank'])
            deposits_rank = int(current_data.iloc[0]['deposits_rank'])
            clients_rank = int(current_data.iloc[0]['clients_rank'])
            partners_rank = int(current_data.iloc[0]['partners_rank'])
            active_partners_rank = int(current_data.iloc[0]['active_partners_rank'])
            etr_rank = int(current_data.iloc[0]['etr_rank'])
            etd_rank = int(current_data.iloc[0]['etd_rank'])
            # Monthly average rankings
            avg_monthly_revenue_rank = int(current_data.iloc[0]['avg_monthly_revenue_rank'])
            avg_monthly_earnings_rank = int(current_data.iloc[0]['avg_monthly_earnings_rank'])
            avg_monthly_deposits_rank = int(current_data.iloc[0]['avg_monthly_deposits_rank'])
            avg_monthly_new_clients_rank = int(current_data.iloc[0]['avg_monthly_new_clients_rank'])
        elif country and 'current_data' in locals() and not current_data.empty:
            earnings_rank = int(current_data.iloc[0]['earnings_rank'])
            revenue_rank = int(current_data.iloc[0]['revenue_rank'])
            deposits_rank = int(current_data.iloc[0]['deposits_rank'])
            clients_rank = int(current_data.iloc[0]['clients_rank'])
            partners_rank = int(current_data.iloc[0]['partners_rank'])  
            active_partners_rank = int(current_data.iloc[0]['active_partners_rank'])
            etr_rank = int(current_data.iloc[0]['etr_rank'])
            etd_rank = int(current_data.iloc[0]['etd_rank'])
            # Monthly average rankings
            avg_monthly_revenue_rank = int(current_data.iloc[0]['avg_monthly_revenue_rank'])
            avg_monthly_earnings_rank = int(current_data.iloc[0]['avg_monthly_earnings_rank'])
            avg_monthly_deposits_rank = int(current_data.iloc[0]['avg_monthly_deposits_rank'])
            avg_monthly_new_clients_rank = int(current_data.iloc[0]['avg_monthly_new_clients_rank'])
        else:
            # Fallback if country/region not found
            earnings_rank = revenue_rank = deposits_rank = clients_rank = partners_rank = active_partners_rank = etr_rank = etd_rank = 1
            avg_monthly_revenue_rank = avg_monthly_earnings_rank = avg_monthly_deposits_rank = avg_monthly_new_clients_rank = 1
        
        # Create summary with real rankings
        summary = {
            'partner_country': country if country else None,
            'partner_region': region if region else None,
            'total_partners': int(total_partners),
            'total_active_partners': int(total_active_partners),
            'total_company_revenue': float(total_company_revenue),
            'total_partner_earnings': float(total_earnings),
            'total_deposits': float(total_deposits),
            'total_new_clients': int(total_clients),
            'partners_rank': partners_rank,
            'active_partners_rank': active_partners_rank,
            'revenue_rank': revenue_rank,
            'earnings_rank': earnings_rank,
            'deposits_rank': deposits_rank,
            'clients_rank': clients_rank,
            'etr_rank': etr_rank,
            'etd_rank': etd_rank,
            # Monthly average rankings
            'avg_monthly_revenue_rank': avg_monthly_revenue_rank,
            'avg_monthly_earnings_rank': avg_monthly_earnings_rank,
            'avg_monthly_deposits_rank': avg_monthly_deposits_rank,
            'avg_monthly_new_clients_rank': avg_monthly_new_clients_rank
        }
        
        # Calculate tier-specific country rankings and monthly rankings
        tier_country_rankings = {}
        monthly_rankings = {}
        
        # For each tier, calculate how this country/region ranks against all other countries/regions
        tiers = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']
        for tier in tiers:
            if region:
                # For regions: calculate tier totals for all regions and rank regions against regions
                try:
                    # Use hardcoded region to country mapping
                    region_country_mapping = REGION_COUNTRY_MAPPING
                    
                    # Calculate tier totals for all regions
                    tier_regions_data = []
                    for region_name, countries in region_country_mapping.items():
                        region_data = partner_data[partner_data['country'].isin(countries)]
                        if not region_data.empty:
                            # Get partners with this tier in this region
                            region_partner_tiers = region_data.groupby('partner_id')['partner_tier'].last().reset_index()
                            tier_partners = region_partner_tiers[region_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()
                            
                            if tier_partners:
                                tier_data = region_data[region_data['partner_id'].isin(tier_partners)]
                                tier_totals = tier_data.agg({
                                    'total_earnings': 'sum',
                                    'company_revenue': 'sum',
                                    'total_deposits': 'sum',
                                    'active_clients': 'sum',
                                    'new_active_clients': 'sum',
                                    'volume_usd': 'sum'
                                })
                                
                                # Calculate ETR and ETD ratios for this tier and region
                                etr_ratio = (tier_totals['total_earnings'] / tier_totals['company_revenue'] * 100) if tier_totals['company_revenue'] > 0 else 0
                                etd_ratio = (tier_totals['total_earnings'] / tier_totals['total_deposits'] * 100) if tier_totals['total_deposits'] > 0 else 0
                                
                                # Calculate monthly averages for this tier and region
                                avg_monthly_revenue = tier_totals['company_revenue'] / month_count
                                avg_monthly_earnings = tier_totals['total_earnings'] / month_count
                                avg_monthly_deposits = tier_totals['total_deposits'] / month_count
                                avg_monthly_new_clients = tier_totals['new_active_clients'] / month_count
                                
                                tier_regions_data.append({
                                    'region': region_name,
                                    'partners_count': len(tier_partners),
                                    'earnings': tier_totals['total_earnings'],
                                    'revenue': tier_totals['company_revenue'],
                                    'deposits': tier_totals['total_deposits'],
                                    'active_clients': tier_totals['active_clients'],
                                    'new_clients': tier_totals['new_active_clients'],
                                    'volume': tier_totals['volume_usd'],
                                    'etr_ratio': etr_ratio,
                                    'etd_ratio': etd_ratio,
                                    'avg_monthly_revenue': avg_monthly_revenue,
                                    'avg_monthly_earnings': avg_monthly_earnings,
                                    'avg_monthly_deposits': avg_monthly_deposits,
                                    'avg_monthly_new_clients': avg_monthly_new_clients
                                })
                            else:
                                # Region has 0 partners in this tier
                                tier_regions_data.append({
                                    'region': region_name,
                                    'partners_count': 0,
                                    'earnings': 0.0,
                                    'revenue': 0.0,
                                    'deposits': 0.0,
                                    'active_clients': 0,
                                    'new_clients': 0,
                                    'volume': 0.0,
                                    'etr_ratio': 0.0,
                                    'etd_ratio': 0.0,
                                    'avg_monthly_revenue': 0.0,
                                    'avg_monthly_earnings': 0.0,
                                    'avg_monthly_deposits': 0.0,
                                    'avg_monthly_new_clients': 0.0
                                })
                    
                    if tier_regions_data:
                        tier_df = pd.DataFrame(tier_regions_data)
                        tier_df['partners_rank'] = tier_df['partners_count'].rank(method='dense', ascending=False)
                        tier_df['earnings_rank'] = tier_df['earnings'].rank(method='dense', ascending=False)
                        tier_df['revenue_rank'] = tier_df['revenue'].rank(method='dense', ascending=False)
                        tier_df['deposits_rank'] = tier_df['deposits'].rank(method='dense', ascending=False)
                        tier_df['active_clients_rank'] = tier_df['active_clients'].rank(method='dense', ascending=False)
                        tier_df['new_clients_rank'] = tier_df['new_clients'].rank(method='dense', ascending=False)
                        tier_df['volume_rank'] = tier_df['volume'].rank(method='dense', ascending=False)
                        tier_df['etr_rank'] = tier_df['etr_ratio'].rank(method='dense', ascending=False)
                        tier_df['etd_rank'] = tier_df['etd_ratio'].rank(method='dense', ascending=False)
                        # Monthly average rankings
                        tier_df['avg_monthly_revenue_rank'] = tier_df['avg_monthly_revenue'].rank(method='dense', ascending=False)
                        tier_df['avg_monthly_earnings_rank'] = tier_df['avg_monthly_earnings'].rank(method='dense', ascending=False)
                        tier_df['avg_monthly_deposits_rank'] = tier_df['avg_monthly_deposits'].rank(method='dense', ascending=False)
                        tier_df['avg_monthly_new_clients_rank'] = tier_df['avg_monthly_new_clients'].rank(method='dense', ascending=False)
                        
                        current_tier_data = tier_df[tier_df['region'] == region]
                        if not current_tier_data.empty:
                            tier_country_rankings[tier] = {
                                'partners_rank': int(current_tier_data.iloc[0]['partners_rank']),
                                'earnings_rank': int(current_tier_data.iloc[0]['earnings_rank']),
                                'revenue_rank': int(current_tier_data.iloc[0]['revenue_rank']),
                                'deposits_rank': int(current_tier_data.iloc[0]['deposits_rank']),
                                'active_clients_rank': int(current_tier_data.iloc[0]['active_clients_rank']),
                                'new_clients_rank': int(current_tier_data.iloc[0]['new_clients_rank']),
                                'volume_rank': int(current_tier_data.iloc[0]['volume_rank']),
                                'etr_rank': int(current_tier_data.iloc[0]['etr_rank']),
                                'etd_rank': int(current_tier_data.iloc[0]['etd_rank']),
                                # Monthly average rankings
                                'avg_monthly_revenue_rank': int(current_tier_data.iloc[0]['avg_monthly_revenue_rank']),
                                'avg_monthly_earnings_rank': int(current_tier_data.iloc[0]['avg_monthly_earnings_rank']),
                                'avg_monthly_deposits_rank': int(current_tier_data.iloc[0]['avg_monthly_deposits_rank']),
                                'avg_monthly_new_clients_rank': int(current_tier_data.iloc[0]['avg_monthly_new_clients_rank'])
                            }
                
                except Exception as e:
                    logger.error(f"Error calculating tier rankings for region {region}: {str(e)}")
                    # Skip this tier if there's an error
                    continue
            else:
                # For countries: calculate tier totals for all countries (existing logic)
                tier_countries_data = []
                all_countries = partner_data['country'].unique()
                
                for other_country in all_countries:
                    if pd.isna(other_country):
                        continue
                        
                    country_data = partner_data[partner_data['country'] == other_country]
                    country_partner_tiers = country_data.groupby('partner_id')['partner_tier'].last().reset_index()
                    tier_partners = country_partner_tiers[country_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()
                    
                    # Include all countries, even those with 0 partners in this tier for proper ranking
                    if tier_partners:
                        tier_data = country_data[country_data['partner_id'].isin(tier_partners)]
                        tier_totals = tier_data.agg({
                            'total_earnings': 'sum',
                            'company_revenue': 'sum',
                            'total_deposits': 'sum',
                            'active_clients': 'sum',
                            'new_active_clients': 'sum',
                            'volume_usd': 'sum'
                        })
                        
                        # Calculate ETR and ETD ratios for this tier and country
                        etr_ratio = (tier_totals['total_earnings'] / tier_totals['company_revenue'] * 100) if tier_totals['company_revenue'] > 0 else 0
                        etd_ratio = (tier_totals['total_earnings'] / tier_totals['total_deposits'] * 100) if tier_totals['total_deposits'] > 0 else 0
                        
                        # Calculate monthly averages for this tier and country
                        avg_monthly_revenue = tier_totals['company_revenue'] / month_count
                        avg_monthly_earnings = tier_totals['total_earnings'] / month_count
                        avg_monthly_deposits = tier_totals['total_deposits'] / month_count
                        avg_monthly_new_clients = tier_totals['new_active_clients'] / month_count
                        
                        tier_countries_data.append({
                            'country': other_country,
                            'partners_count': len(tier_partners),
                            'earnings': tier_totals['total_earnings'],
                            'revenue': tier_totals['company_revenue'],
                            'deposits': tier_totals['total_deposits'],
                            'active_clients': tier_totals['active_clients'],
                            'new_clients': tier_totals['new_active_clients'],
                            'volume': tier_totals['volume_usd'],
                            'etr_ratio': etr_ratio,
                            'etd_ratio': etd_ratio,
                            'avg_monthly_revenue': avg_monthly_revenue,
                            'avg_monthly_earnings': avg_monthly_earnings,
                            'avg_monthly_deposits': avg_monthly_deposits,
                            'avg_monthly_new_clients': avg_monthly_new_clients
                        })
                    else:
                        # Country has 0 partners in this tier - add with zero values for proper ranking
                        tier_countries_data.append({
                            'country': other_country,
                            'partners_count': 0,
                            'earnings': 0.0,
                            'revenue': 0.0,
                            'deposits': 0.0,
                            'active_clients': 0,
                            'new_clients': 0,
                            'volume': 0.0,
                            'etr_ratio': 0.0,
                            'etd_ratio': 0.0,
                            'avg_monthly_revenue': 0.0,
                            'avg_monthly_earnings': 0.0,
                            'avg_monthly_deposits': 0.0,
                            'avg_monthly_new_clients': 0.0
                        })
                
                if tier_countries_data:
                    tier_df = pd.DataFrame(tier_countries_data)
                    tier_df['partners_rank'] = tier_df['partners_count'].rank(method='dense', ascending=False)
                    tier_df['earnings_rank'] = tier_df['earnings'].rank(method='dense', ascending=False)
                    tier_df['revenue_rank'] = tier_df['revenue'].rank(method='dense', ascending=False)
                    tier_df['deposits_rank'] = tier_df['deposits'].rank(method='dense', ascending=False)
                    tier_df['active_clients_rank'] = tier_df['active_clients'].rank(method='dense', ascending=False)
                    tier_df['new_clients_rank'] = tier_df['new_clients'].rank(method='dense', ascending=False)
                    tier_df['volume_rank'] = tier_df['volume'].rank(method='dense', ascending=False)
                    tier_df['etr_rank'] = tier_df['etr_ratio'].rank(method='dense', ascending=False)
                    tier_df['etd_rank'] = tier_df['etd_ratio'].rank(method='dense', ascending=False)
                    # Monthly average rankings
                    tier_df['avg_monthly_revenue_rank'] = tier_df['avg_monthly_revenue'].rank(method='dense', ascending=False)
                    tier_df['avg_monthly_earnings_rank'] = tier_df['avg_monthly_earnings'].rank(method='dense', ascending=False)
                    tier_df['avg_monthly_deposits_rank'] = tier_df['avg_monthly_deposits'].rank(method='dense', ascending=False)
                    tier_df['avg_monthly_new_clients_rank'] = tier_df['avg_monthly_new_clients'].rank(method='dense', ascending=False)
                    
                    current_tier_data = tier_df[tier_df['country'] == country]
                    if not current_tier_data.empty:
                        tier_country_rankings[tier] = {
                            'partners_rank': int(current_tier_data.iloc[0]['partners_rank']),
                            'earnings_rank': int(current_tier_data.iloc[0]['earnings_rank']),
                            'revenue_rank': int(current_tier_data.iloc[0]['revenue_rank']),
                            'deposits_rank': int(current_tier_data.iloc[0]['deposits_rank']),
                            'active_clients_rank': int(current_tier_data.iloc[0]['active_clients_rank']),
                            'new_clients_rank': int(current_tier_data.iloc[0]['new_clients_rank']),
                            'volume_rank': int(current_tier_data.iloc[0]['volume_rank']),
                            'etr_rank': int(current_tier_data.iloc[0]['etr_rank']),
                            'etd_rank': int(current_tier_data.iloc[0]['etd_rank']),
                            # Monthly average rankings
                            'avg_monthly_revenue_rank': int(current_tier_data.iloc[0]['avg_monthly_revenue_rank']),
                            'avg_monthly_earnings_rank': int(current_tier_data.iloc[0]['avg_monthly_earnings_rank']),
                            'avg_monthly_deposits_rank': int(current_tier_data.iloc[0]['avg_monthly_deposits_rank']),
                            'avg_monthly_new_clients_rank': int(current_tier_data.iloc[0]['avg_monthly_new_clients_rank'])
                        }
        
        # Calculate monthly rankings for each metric
        # UPDATED: Calculate both overall and tier-specific monthly rankings
        tier_monthly_rankings = {}  # Structure: {tier: {month: {ranking_data}}}
        
        for month_str in monthly_data.keys():
            monthly_rankings[month_str] = {}
            
            # Get all data for this month for comparison
            month_date = pd.to_datetime(month_str, format='%b %Y')
            month_data_all = partner_data[partner_data['month'] == month_date]
            
            if not month_data_all.empty:
                if region:
                    # For regions: calculate region vs region rankings
                    try:
                        # Use hardcoded region to country mapping
                        region_country_mapping = REGION_COUNTRY_MAPPING
                        
                        # Calculate metrics for each region by aggregating its countries' data
                        regions_month_data = []
                        for region_name, countries in region_country_mapping.items():
                            region_month_data = month_data_all[month_data_all['country'].isin(countries)]
                            if not region_month_data.empty:
                                # Aggregate region metrics for this month
                                region_month_totals = region_month_data.agg({
                                    'total_earnings': 'sum',
                                    'company_revenue': 'sum',
                                    'total_deposits': 'sum',
                                    'active_clients': 'sum',
                                    'new_active_clients': 'sum',
                                    'volume_usd': 'sum',
                                    'partner_id': 'nunique'
                                })
                                
                                # Calculate ETR and ETD ratios for this month and region
                                etr_ratio = (region_month_totals['total_earnings'] / region_month_totals['company_revenue'] * 100) if region_month_totals['company_revenue'] > 0 else 0
                                etd_ratio = (region_month_totals['total_earnings'] / region_month_totals['total_deposits'] * 100) if region_month_totals['total_deposits'] > 0 else 0
                                
                                regions_month_data.append({
                                    'region': region_name,
                                    'partners_count': region_month_totals['partner_id'],
                                    'earnings': region_month_totals['total_earnings'],
                                    'revenue': region_month_totals['company_revenue'],
                                    'deposits': region_month_totals['total_deposits'],
                                    'active_clients': region_month_totals['active_clients'],
                                    'new_clients': region_month_totals['new_active_clients'],
                                    'volume': region_month_totals['volume_usd'],
                                    'etr_ratio': etr_ratio,
                                    'etd_ratio': etd_ratio
                                })
                            else:
                                # Region has no data for this month
                                regions_month_data.append({
                                    'region': region_name,
                                    'partners_count': 0,
                                    'earnings': 0.0,
                                    'revenue': 0.0,
                                    'deposits': 0.0,
                                    'active_clients': 0,
                                    'new_clients': 0,
                                    'volume': 0.0,
                                    'etr_ratio': 0.0,
                                    'etd_ratio': 0.0
                                })
                        
                        if regions_month_data:
                            month_df = pd.DataFrame(regions_month_data)
                            month_df['partners_rank'] = month_df['partners_count'].rank(method='dense', ascending=False)
                            month_df['earnings_rank'] = month_df['earnings'].rank(method='dense', ascending=False)
                            month_df['revenue_rank'] = month_df['revenue'].rank(method='dense', ascending=False)
                            month_df['deposits_rank'] = month_df['deposits'].rank(method='dense', ascending=False)
                            month_df['active_clients_rank'] = month_df['active_clients'].rank(method='dense', ascending=False)
                            month_df['new_clients_rank'] = month_df['new_clients'].rank(method='dense', ascending=False)
                            month_df['volume_rank'] = month_df['volume'].rank(method='dense', ascending=False)
                            month_df['etr_rank'] = month_df['etr_ratio'].rank(method='dense', ascending=False)
                            month_df['etd_rank'] = month_df['etd_ratio'].rank(method='dense', ascending=False)
                            
                            current_month_data = month_df[month_df['region'] == region]
                            if not current_month_data.empty:
                                monthly_rankings[month_str] = {
                                    'partners_rank': int(current_month_data.iloc[0]['partners_rank']),
                                    'earnings_rank': int(current_month_data.iloc[0]['earnings_rank']),
                                    'revenue_rank': int(current_month_data.iloc[0]['revenue_rank']),
                                    'deposits_rank': int(current_month_data.iloc[0]['deposits_rank']),
                                    'active_clients_rank': int(current_month_data.iloc[0]['active_clients_rank']),
                                    'new_clients_rank': int(current_month_data.iloc[0]['new_clients_rank']),
                                    'volume_rank': int(current_month_data.iloc[0]['volume_rank']),
                                    'etr_rank': int(current_month_data.iloc[0]['etr_rank']),
                                    'etd_rank': int(current_month_data.iloc[0]['etd_rank'])
                                }
                    except Exception as e:
                        logger.error(f"Error calculating region monthly rankings for {month_str}: {str(e)}")
                else:
                    # For countries: original country vs country rankings logic
                    countries_month_data = []
                    all_countries = month_data_all['country'].unique()
                    
                    for other_country in all_countries:
                        if pd.isna(other_country):
                            continue
                            
                        country_month_data = month_data_all[month_data_all['country'] == other_country]
                        country_totals = country_month_data.agg({
                            'total_earnings': 'sum',
                            'company_revenue': 'sum',
                            'total_deposits': 'sum',
                            'active_clients': 'sum',
                            'new_active_clients': 'sum',
                            'volume_usd': 'sum',
                            'partner_id': 'nunique'  # Count unique partners for this country in this month
                        })
                        
                        # Calculate ETR and ETD ratios for this month and country
                        etr_ratio = (country_totals['total_earnings'] / country_totals['company_revenue'] * 100) if country_totals['company_revenue'] > 0 else 0
                        etd_ratio = (country_totals['total_earnings'] / country_totals['total_deposits'] * 100) if country_totals['total_deposits'] > 0 else 0
                        
                        countries_month_data.append({
                            'country': other_country,
                            'partners_count': country_totals['partner_id'],
                            'earnings': country_totals['total_earnings'],
                            'revenue': country_totals['company_revenue'],
                            'deposits': country_totals['total_deposits'],
                            'active_clients': country_totals['active_clients'],
                            'new_clients': country_totals['new_active_clients'],
                            'volume': country_totals['volume_usd'],
                            'etr_ratio': etr_ratio,
                            'etd_ratio': etd_ratio
                        })
                    
                    if countries_month_data:
                        month_df = pd.DataFrame(countries_month_data)
                        month_df['partners_rank'] = month_df['partners_count'].rank(method='dense', ascending=False)
                        month_df['earnings_rank'] = month_df['earnings'].rank(method='dense', ascending=False)
                        month_df['revenue_rank'] = month_df['revenue'].rank(method='dense', ascending=False)
                        month_df['deposits_rank'] = month_df['deposits'].rank(method='dense', ascending=False)
                        month_df['active_clients_rank'] = month_df['active_clients'].rank(method='dense', ascending=False)
                        month_df['new_clients_rank'] = month_df['new_clients'].rank(method='dense', ascending=False)
                        month_df['volume_rank'] = month_df['volume'].rank(method='dense', ascending=False)
                        month_df['etr_rank'] = month_df['etr_ratio'].rank(method='dense', ascending=False)
                        month_df['etd_rank'] = month_df['etd_ratio'].rank(method='dense', ascending=False)
                        
                        current_month_data = month_df[month_df['country'] == country]
                        if not current_month_data.empty:
                            monthly_rankings[month_str] = {
                                'partners_rank': int(current_month_data.iloc[0]['partners_rank']),
                                'earnings_rank': int(current_month_data.iloc[0]['earnings_rank']),
                                'revenue_rank': int(current_month_data.iloc[0]['revenue_rank']),
                                'deposits_rank': int(current_month_data.iloc[0]['deposits_rank']),
                                'active_clients_rank': int(current_month_data.iloc[0]['active_clients_rank']),
                                'new_clients_rank': int(current_month_data.iloc[0]['new_clients_rank']),
                                'volume_rank': int(current_month_data.iloc[0]['volume_rank']),
                                'etr_rank': int(current_month_data.iloc[0]['etr_rank']),
                                'etd_rank': int(current_month_data.iloc[0]['etd_rank'])
                            }

        # Calculate tier-specific monthly rankings
        for tier in ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']:
            tier_monthly_rankings[tier] = {}
            
            for month_str in monthly_data.keys():
                month_date = pd.to_datetime(month_str, format='%b %Y')
                month_data_all = partner_data[partner_data['month'] == month_date]
                
                if not month_data_all.empty:
                    if region:
                        # For regions: calculate tier-specific region vs region rankings
                        try:
                            # Use hardcoded region to country mapping (reuse from above)
                            region_country_mapping = REGION_COUNTRY_MAPPING
                            
                            # Calculate tier-specific data for all regions for this month
                            tier_regions_month_data = []
                            for region_name, countries in region_country_mapping.items():
                                region_month_data = month_data_all[month_data_all['country'].isin(countries)]
                                if not region_month_data.empty:
                                    # Get partners of this tier for this region in this month
                                    region_partner_tiers = region_month_data.groupby('partner_id')['partner_tier'].last().reset_index()
                                    tier_partners = region_partner_tiers[region_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()
                                    
                                    if tier_partners:
                                        tier_region_month_data = region_month_data[region_month_data['partner_id'].isin(tier_partners)]
                                        tier_region_month_totals = tier_region_month_data.agg({
                                            'total_earnings': 'sum',
                                            'company_revenue': 'sum',
                                            'total_deposits': 'sum',
                                            'active_clients': 'sum',
                                            'new_active_clients': 'sum',
                                            'volume_usd': 'sum',
                                            'partner_id': 'nunique'
                                        })
                                        
                                        etr_ratio = (tier_region_month_totals['total_earnings'] / tier_region_month_totals['company_revenue'] * 100) if tier_region_month_totals['company_revenue'] > 0 else 0
                                        etd_ratio = (tier_region_month_totals['total_earnings'] / tier_region_month_totals['total_deposits'] * 100) if tier_region_month_totals['total_deposits'] > 0 else 0
                                        
                                        tier_regions_month_data.append({
                                            'region': region_name,
                                            'partners_count': tier_region_month_totals['partner_id'],
                                            'earnings': tier_region_month_totals['total_earnings'],
                                            'revenue': tier_region_month_totals['company_revenue'],
                                            'deposits': tier_region_month_totals['total_deposits'],
                                            'active_clients': tier_region_month_totals['active_clients'],
                                            'new_clients': tier_region_month_totals['new_active_clients'],
                                            'volume': tier_region_month_totals['volume_usd'],
                                            'etr_ratio': etr_ratio,
                                            'etd_ratio': etd_ratio
                                        })
                                    else:
                                        # Region has 0 partners in this tier for this month
                                        tier_regions_month_data.append({
                                            'region': region_name,
                                            'partners_count': 0,
                                            'earnings': 0.0,
                                            'revenue': 0.0,
                                            'deposits': 0.0,
                                            'active_clients': 0,
                                            'new_clients': 0,
                                            'volume': 0.0,
                                            'etr_ratio': 0.0,
                                            'etd_ratio': 0.0
                                        })
                                else:
                                    # Region has no data for this month
                                    tier_regions_month_data.append({
                                        'region': region_name,
                                        'partners_count': 0,
                                        'earnings': 0.0,
                                        'revenue': 0.0,
                                        'deposits': 0.0,
                                        'active_clients': 0,
                                        'new_clients': 0,
                                        'volume': 0.0,
                                        'etr_ratio': 0.0,
                                        'etd_ratio': 0.0
                                    })
                            
                            if tier_regions_month_data:
                                tier_month_df = pd.DataFrame(tier_regions_month_data)
                                tier_month_df['partners_rank'] = tier_month_df['partners_count'].rank(method='dense', ascending=False)
                                tier_month_df['earnings_rank'] = tier_month_df['earnings'].rank(method='dense', ascending=False)
                                tier_month_df['revenue_rank'] = tier_month_df['revenue'].rank(method='dense', ascending=False)
                                tier_month_df['deposits_rank'] = tier_month_df['deposits'].rank(method='dense', ascending=False)
                                tier_month_df['active_clients_rank'] = tier_month_df['active_clients'].rank(method='dense', ascending=False)
                                tier_month_df['new_clients_rank'] = tier_month_df['new_clients'].rank(method='dense', ascending=False)
                                tier_month_df['volume_rank'] = tier_month_df['volume'].rank(method='dense', ascending=False)
                                tier_month_df['etr_rank'] = tier_month_df['etr_ratio'].rank(method='dense', ascending=False)
                                tier_month_df['etd_rank'] = tier_month_df['etd_ratio'].rank(method='dense', ascending=False)
                                
                                current_tier_month_data = tier_month_df[tier_month_df['region'] == region]
                                if not current_tier_month_data.empty:
                                    tier_monthly_rankings[tier][month_str] = {
                                        'partners_rank': int(current_tier_month_data.iloc[0]['partners_rank']),
                                        'earnings_rank': int(current_tier_month_data.iloc[0]['earnings_rank']),
                                        'revenue_rank': int(current_tier_month_data.iloc[0]['revenue_rank']),
                                        'deposits_rank': int(current_tier_month_data.iloc[0]['deposits_rank']),
                                        'active_clients_rank': int(current_tier_month_data.iloc[0]['active_clients_rank']),
                                        'new_clients_rank': int(current_tier_month_data.iloc[0]['new_clients_rank']),
                                        'volume_rank': int(current_tier_month_data.iloc[0]['volume_rank']),
                                        'etr_rank': int(current_tier_month_data.iloc[0]['etr_rank']),
                                        'etd_rank': int(current_tier_month_data.iloc[0]['etd_rank'])
                                    }
                        except Exception as e:
                            logger.error(f"Error calculating region tier monthly rankings for {tier} {month_str}: {str(e)}")
                    else:
                        # For countries: original tier-specific country vs country rankings logic
                        tier_countries_month_data = []
                        all_countries = month_data_all['country'].unique()
                        
                        for other_country in all_countries:
                            if pd.isna(other_country):
                                continue
                                
                            country_month_data = month_data_all[month_data_all['country'] == other_country]
                            # Get partners of this tier for this country in this month
                            country_partner_tiers = country_month_data.groupby('partner_id')['partner_tier'].last().reset_index()
                            tier_partners = country_partner_tiers[country_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()
                            
                            if tier_partners:
                                tier_month_data = country_month_data[country_month_data['partner_id'].isin(tier_partners)]
                                tier_month_totals = tier_month_data.agg({
                                    'total_earnings': 'sum',
                                    'company_revenue': 'sum',
                                    'total_deposits': 'sum',
                                    'active_clients': 'sum',
                                    'new_active_clients': 'sum',
                                    'volume_usd': 'sum',
                                    'partner_id': 'nunique'
                                })
                                
                                etr_ratio = (tier_month_totals['total_earnings'] / tier_month_totals['company_revenue'] * 100) if tier_month_totals['company_revenue'] > 0 else 0
                                etd_ratio = (tier_month_totals['total_earnings'] / tier_month_totals['total_deposits'] * 100) if tier_month_totals['total_deposits'] > 0 else 0
                                
                                tier_countries_month_data.append({
                                    'country': other_country,
                                    'partners_count': tier_month_totals['partner_id'],
                                    'earnings': tier_month_totals['total_earnings'],
                                    'revenue': tier_month_totals['company_revenue'],
                                    'deposits': tier_month_totals['total_deposits'],
                                    'active_clients': tier_month_totals['active_clients'],
                                    'new_clients': tier_month_totals['new_active_clients'],
                                    'volume': tier_month_totals['volume_usd'],
                                    'etr_ratio': etr_ratio,
                                    'etd_ratio': etd_ratio
                                })
                            else:
                                # Country has 0 partners in this tier for this month
                                tier_countries_month_data.append({
                                    'country': other_country,
                                    'partners_count': 0,
                                    'earnings': 0.0,
                                    'revenue': 0.0,
                                    'deposits': 0.0,
                                    'active_clients': 0,
                                    'new_clients': 0,
                                    'volume': 0.0,
                                    'etr_ratio': 0.0,
                                    'etd_ratio': 0.0
                                })
                        
                        if tier_countries_month_data:
                            tier_month_df = pd.DataFrame(tier_countries_month_data)
                            tier_month_df['partners_rank'] = tier_month_df['partners_count'].rank(method='dense', ascending=False)
                            tier_month_df['earnings_rank'] = tier_month_df['earnings'].rank(method='dense', ascending=False)
                            tier_month_df['revenue_rank'] = tier_month_df['revenue'].rank(method='dense', ascending=False)
                            tier_month_df['deposits_rank'] = tier_month_df['deposits'].rank(method='dense', ascending=False)
                            tier_month_df['active_clients_rank'] = tier_month_df['active_clients'].rank(method='dense', ascending=False)
                            tier_month_df['new_clients_rank'] = tier_month_df['new_clients'].rank(method='dense', ascending=False)
                            tier_month_df['volume_rank'] = tier_month_df['volume'].rank(method='dense', ascending=False)
                            tier_month_df['etr_rank'] = tier_month_df['etr_ratio'].rank(method='dense', ascending=False)
                            tier_month_df['etd_rank'] = tier_month_df['etd_ratio'].rank(method='dense', ascending=False)
                            
                            current_tier_month_data = tier_month_df[tier_month_df['country'] == country]
                            if not current_tier_month_data.empty:
                                tier_monthly_rankings[tier][month_str] = {
                                    'partners_rank': int(current_tier_month_data.iloc[0]['partners_rank']),
                                    'earnings_rank': int(current_tier_month_data.iloc[0]['earnings_rank']),
                                    'revenue_rank': int(current_tier_month_data.iloc[0]['revenue_rank']),
                                    'deposits_rank': int(current_tier_month_data.iloc[0]['deposits_rank']),
                                    'active_clients_rank': int(current_tier_month_data.iloc[0]['active_clients_rank']),
                                    'new_clients_rank': int(current_tier_month_data.iloc[0]['new_clients_rank']),
                                    'volume_rank': int(current_tier_month_data.iloc[0]['volume_rank']),
                                    'etr_rank': int(current_tier_month_data.iloc[0]['etr_rank']),
                                    'etd_rank': int(current_tier_month_data.iloc[0]['etd_rank'])
                                }

        # Calculate global totals for percentage calculations (matching Partner Overview methodology)
        global_summary = partner_data.groupby('partner_id').agg({
            'partner_tier': 'last',
            'total_earnings': 'sum',
            'total_deposits': 'sum',
            'active_clients': 'last',
            'new_active_clients': 'sum'
        }).reset_index()
        
        # UPDATED: Match Partner Overview - only use ACTIVE partners (exclude Inactive)
        active_global_summary = global_summary[global_summary['partner_tier'] != 'Inactive']
        
        global_totals = {
            'total_active_partners': len(active_global_summary),
            'total_company_revenue': float(active_global_summary['total_earnings'].sum()),  # Use total_earnings as revenue (matching Partner Overview)
            'total_partner_earnings': float(active_global_summary['total_earnings'].sum()),
            'total_deposits': float(active_global_summary['total_deposits'].sum()),
            'total_new_clients': int(active_global_summary['new_active_clients'].sum())
        }
        
        # Calculate global tier totals (matching Partner Overview methodology)
        tier_totals = {}
        for tier in ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive']:
            tier_data = global_summary[global_summary['partner_tier'] == tier]
            if not tier_data.empty:
                tier_totals[tier] = {
                    'total_active_partners': len(tier_data),
                    'total_company_revenue': float(tier_data['total_earnings'].sum()),  # Use total_earnings as revenue
                    'total_partner_earnings': float(tier_data['total_earnings'].sum()),
                    'total_deposits': float(tier_data['total_deposits'].sum()),
                    'total_new_clients': int(tier_data['new_active_clients'].sum())
                }
            else:
                tier_totals[tier] = {
                    'total_active_partners': 0,
                    'total_company_revenue': 0.0,
                    'total_partner_earnings': 0.0,
                    'total_deposits': 0.0,
                    'total_new_clients': 0
                }
        
        global_totals['tier_totals'] = tier_totals

        # ENHANCEMENT: Add ranking information to monthly tier data
        for month_str in monthly_data.keys():
            # Add overall monthly rankings (non-tier-specific) to the monthly data
            if month_str in monthly_rankings:
                for tier in monthly_data[month_str].keys():
                    if tier in monthly_data[month_str]:
                        monthly_data[month_str][tier].update({
                            'active_clients_rank': monthly_rankings[month_str].get('active_clients_rank', 0),
                            'earnings_rank': monthly_rankings[month_str].get('earnings_rank', 0),
                            'revenue_rank': monthly_rankings[month_str].get('revenue_rank', 0),
                            'deposits_rank': monthly_rankings[month_str].get('deposits_rank', 0),
                            'partners_rank': monthly_rankings[month_str].get('partners_rank', 0),
                            'new_clients_rank': monthly_rankings[month_str].get('new_clients_rank', 0),
                            'volume_rank': monthly_rankings[month_str].get('volume_rank', 0)
                        })
            
            # Add tier-specific monthly rankings to the monthly data
            for tier in monthly_data[month_str].keys():
                if tier in tier_monthly_rankings and month_str in tier_monthly_rankings[tier]:
                    tier_ranks = tier_monthly_rankings[tier][month_str]
                    monthly_data[month_str][tier].update({
                        'tier_active_clients_rank': tier_ranks.get('active_clients_rank', 0),
                        'tier_earnings_rank': tier_ranks.get('earnings_rank', 0),
                        'tier_revenue_rank': tier_ranks.get('revenue_rank', 0),
                        'tier_deposits_rank': tier_ranks.get('deposits_rank', 0),
                        'tier_partners_rank': tier_ranks.get('partners_rank', 0),
                        'tier_new_clients_rank': tier_ranks.get('new_clients_rank', 0),
                        'tier_volume_rank': tier_ranks.get('volume_rank', 0)
                    })

        analytics_data = {
            'summary': summary,
            'monthly_tier_data': monthly_data,
            'tier_country_rankings': tier_country_rankings,
            'monthly_rankings': monthly_rankings,
            'tier_monthly_rankings': tier_monthly_rankings,  # NEW: Tier-specific monthly rankings
            'country_rankings': {},  # Not applicable for single country view
            'available_months': list(monthly_data.keys()) if monthly_data else [],  # Already sorted chronologically
            'global_totals': global_totals
        }
        
        return jsonify({
            'success': True,
            'data': analytics_data,
            'country': country,
            'region': region
        })
        
    except Exception as e:
        logger.error(f"Error getting country tier analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tier-detail', methods=['GET'])
def get_tier_detail():
    """Get detailed tier performance data with rankings for tier detail modal"""
    try:
        country = request.args.get('country')
        region = request.args.get('region')
        tier = request.args.get('tier')
        month = request.args.get('month')
        
        if not country and not region:
            return jsonify({'error': 'Either country or region parameter is required'}), 400
        
        detail_data = db.get_tier_detail_data(
            country=country, 
            region=region, 
            tier=tier, 
            month=month
        )
        
        return jsonify({
            'success': True,
            'data': detail_data,
            'filters': {
                'country': country,
                'region': region,
                'tier': tier,
                'month': month
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting tier detail data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/monthly-country-funnel', methods=['GET'])
def get_monthly_country_funnel():
    """Get monthly funnel data for a specific country/region with rankings"""
    try:
        country = request.args.get('country')
        region = request.args.get('region')
        
        # Handle URL encoding where + should become spaces
        if region:
            region = region.replace('+', ' ')
        if country:
            country = country.replace('+', ' ')
        
        if not country and not region:
            return jsonify({'error': 'Either country or region parameter is required'}), 400
        
        funnel_data = db.get_monthly_country_funnel_data(country=country, region=region)
        
        return jsonify({
            'success': True,
            'data': funnel_data,
            'country': country,
            'region': region
        })
        
    except Exception as e:
        logger.error(f"Error getting monthly country funnel data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tier-performance', methods=['GET'])
def get_tier_performance():
    """Get detailed tier performance data with rankings for a specific tier and country"""
    try:
        if partner_data is None:
            return jsonify({'error': 'No data available'}), 400
        
        country = request.args.get('country')
        region = request.args.get('region')
        tier = request.args.get('tier')
        
        if not country and not region:
            return jsonify({'error': 'Either country or region parameter is required'}), 400
            
        if not tier:
            return jsonify({'error': 'Tier parameter is required'}), 400
        
        # Filter CSV data by country or region and tier
        filtered_data = partner_data.copy()
        
        if country:
            filtered_data = filtered_data[filtered_data['country'] == country]
        elif region:
            filtered_data = filtered_data[filtered_data['region'] == region]
        
        # Filter by partners who have the specified tier (latest tier)
        partner_latest_tier = filtered_data.groupby('partner_id')['partner_tier'].last().reset_index()
        tier_partners = partner_latest_tier[partner_latest_tier['partner_tier'] == tier]['partner_id'].tolist()
        
        if not tier_partners:
            return jsonify({
                'success': True,
                'data': [],
                'tier': tier,
                'country': country,
                'region': region
            })
        
        # Get data only for partners with this tier
        tier_filtered_data = filtered_data[filtered_data['partner_id'].isin(tier_partners)]
        
        # Get monthly performance for these partners
        monthly_performance = tier_filtered_data.groupby('month').agg({
            'partner_id': 'nunique',
            'total_earnings': 'sum',
            'company_revenue': 'sum',
            'total_deposits': 'sum',
            'active_clients': 'sum',
            'new_active_clients': 'sum',
            'volume_usd': 'sum'
        }).reset_index()
        
        # Calculate EtR and EtD ratios
        monthly_performance['etr_ratio'] = monthly_performance.apply(
            lambda row: round((row['total_earnings'] / row['company_revenue'] * 100), 2) 
            if row['company_revenue'] > 0 else 0, axis=1
        )
        monthly_performance['etd_ratio'] = monthly_performance.apply(
            lambda row: round((row['total_earnings'] / row['total_deposits'] * 100), 2) 
            if row['total_deposits'] > 0 else 0, axis=1
        )
        
        # Now calculate rankings compared to ALL countries for this tier
        # Get all countries' data for this tier to calculate rankings
        all_countries_tier_data = []
        
        for compare_country in partner_data['country'].unique():
            if pd.isna(compare_country):
                continue
                
            country_data = partner_data[partner_data['country'] == compare_country]
            country_partner_tiers = country_data.groupby('partner_id')['partner_tier'].last().reset_index()
            country_tier_partners = country_partner_tiers[country_partner_tiers['partner_tier'] == tier]['partner_id'].tolist()
            
            if not country_tier_partners:
                continue
                
            country_tier_data = country_data[country_data['partner_id'].isin(country_tier_partners)]
            
            country_monthly = country_tier_data.groupby('month').agg({
                'total_earnings': 'sum',
                'company_revenue': 'sum',
                'total_deposits': 'sum',
                'active_clients': 'sum',
                'new_active_clients': 'sum',
                'volume_usd': 'sum'
            }).reset_index()
            
            for _, row in country_monthly.iterrows():
                all_countries_tier_data.append({
                    'country': compare_country,
                    'month': row['month'],
                    'total_earnings': row['total_earnings'],
                    'company_revenue': row['company_revenue'],
                    'total_deposits': row['total_deposits'],
                    'active_clients': row['active_clients'],
                    'new_active_clients': row['new_active_clients'],
                    'volume_usd': row['volume_usd']
                })
        
        # Convert to DataFrame for ranking calculations
        all_countries_df = pd.DataFrame(all_countries_tier_data)
        
        # Sort monthly performance by month descending
        monthly_performance = monthly_performance.sort_values('month', ascending=False)
        
        # Calculate rankings for each month
        formatted_results = []
        for _, row in monthly_performance.iterrows():
            month_str = row['month'].strftime('%b %Y')
            
            # Get rankings for this month across all countries
            month_data = all_countries_df[all_countries_df['month'] == row['month']]
            
            if not month_data.empty:
                # Calculate rankings (lower rank = better performance)
                month_data_sorted = month_data.copy()
                month_data_sorted['earnings_rank'] = month_data_sorted['total_earnings'].rank(method='dense', ascending=False)
                month_data_sorted['revenue_rank'] = month_data_sorted['company_revenue'].rank(method='dense', ascending=False)
                month_data_sorted['deposits_rank'] = month_data_sorted['total_deposits'].rank(method='dense', ascending=False)
                month_data_sorted['clients_rank'] = month_data_sorted['active_clients'].rank(method='dense', ascending=False)
                month_data_sorted['new_clients_rank'] = month_data_sorted['new_active_clients'].rank(method='dense', ascending=False)
                month_data_sorted['volume_rank'] = month_data_sorted['volume_usd'].rank(method='dense', ascending=False)
                
                # Find current country's ranking
                current_country_rank = month_data_sorted[month_data_sorted['country'] == (country if country else region)]
                
                if not current_country_rank.empty:
                    rank_data = current_country_rank.iloc[0]
                    earnings_rank = int(rank_data['earnings_rank'])
                    revenue_rank = int(rank_data['revenue_rank'])
                    deposits_rank = int(rank_data['deposits_rank'])
                    clients_rank = int(rank_data['clients_rank'])
                    new_clients_rank = int(rank_data['new_clients_rank'])
                    volume_rank = int(rank_data['volume_rank'])
                else:
                    # Fallback rankings
                    earnings_rank = revenue_rank = deposits_rank = clients_rank = new_clients_rank = volume_rank = 1
            else:
                # Fallback rankings
                earnings_rank = revenue_rank = deposits_rank = clients_rank = new_clients_rank = volume_rank = 1
            
            formatted_results.append({
                'month': month_str,
                'tier': tier,
                'total_earnings': float(row['total_earnings']),
                'earnings_rank': earnings_rank,
                'company_revenue': float(row['company_revenue']),
                'revenue_rank': revenue_rank,
                'etr_ratio': float(row['etr_ratio']),
                'total_deposits': float(row['total_deposits']),
                'deposits_rank': deposits_rank,
                'etd_ratio': float(row['etd_ratio']),
                'active_clients': int(row['active_clients']),
                'clients_rank': clients_rank,
                'new_clients': int(row['new_active_clients']),
                'new_clients_rank': new_clients_rank,
                'volume': float(row['volume_usd']),
                'volume_rank': volume_rank
            })
        
        return jsonify({
            'success': True,
            'data': formatted_results,
            'tier': tier,
            'country': country,
            'region': region,
            'total_months': len(formatted_results)
        })
        
    except Exception as e:
        logger.error(f"Error getting tier performance data: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting PDash backend server...")
    logger.info("Database connection pool initialized successfully")
    app.run(debug=True, host='0.0.0.0', port=5003) 