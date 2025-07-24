import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupabaseDB:
    def __init__(self):
        self.db_params = {
            'host': os.getenv('host'),
            'port': os.getenv('port'),
            'database': os.getenv('dbname'),
            'user': os.getenv('user'),
            'password': os.getenv('password')
        }
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_params)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Successfully connected to Supabase database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise e
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")
    
    def get_partner_funnel_data(self, partner_id: str) -> List[Dict[str, Any]]:
        """
        Get monthly funnel performance data for a specific partner with Demo, Real, Deposit, Traded stages.
        
        Args:
            partner_id (str): The partner ID to get funnel data for
            
        Returns:
            List[Dict]: Monthly funnel data with demo, real, deposit, traded counts and conversion rates
        """
        try:
            if not self.conn:
                self.connect()
            
            # First, let's run diagnostic queries to understand the data inconsistency
            table_name = "client.user_profile"
            
            # Test 1: Check total counts with and without is_internal filter
            logger.info("=== DIAGNOSTIC QUERIES ===")
            
            # Count with is_internal = FALSE (our current filter)
            test_query1 = """
            SELECT 
                'excluding_internal' as filter_type,
                COUNT(*) as total_records,
                COUNT(DISTINCT CASE WHEN demo_joined_date IS NOT NULL OR real_joined_date IS NOT NULL THEN binary_user_id END) as users_with_join_date
            FROM client.user_profile 
            WHERE affiliated_partner_id = %s AND is_internal = FALSE
            """
            
            # Count with ALL records (including internal)
            test_query2 = """
            SELECT 
                'including_internal' as filter_type,
                COUNT(*) as total_records,
                COUNT(DISTINCT CASE WHEN demo_joined_date IS NOT NULL OR real_joined_date IS NOT NULL THEN binary_user_id END) as users_with_join_date
            FROM client.user_profile 
            WHERE affiliated_partner_id = %s
            """
            
            # July 2025 specific check
            test_query3 = """
            SELECT 
                'july_2025_breakdown' as period,
                COUNT(DISTINCT binary_user_id) as signups,
                COUNT(DISTINCT CASE WHEN first_deposit_date IS NOT NULL THEN binary_user_id END) as deposits,
                COUNT(DISTINCT CASE WHEN first_trade_date IS NOT NULL THEN binary_user_id END) as trades,
                COUNT(DISTINCT CASE WHEN is_internal = TRUE THEN binary_user_id END) as internal_users
            FROM client.user_profile 
            WHERE affiliated_partner_id = %s 
                AND DATE_TRUNC('month', COALESCE(demo_joined_date, real_joined_date)) = '2025-07-01'
            """
            
            try:
                logger.info("Running diagnostic queries...")
                
                # Query 1: Excluding internal
                self.cursor.execute(test_query1, (partner_id,))
                result1 = self.cursor.fetchone()
                logger.info(f"Excluding internal: {dict(result1)}")
                
                # Query 2: Including internal  
                self.cursor.execute(test_query2, (partner_id,))
                result2 = self.cursor.fetchone()
                logger.info(f"Including internal: {dict(result2)}")
                
                # Query 3: July breakdown
                self.cursor.execute(test_query3, (partner_id,))
                result3 = self.cursor.fetchone()
                logger.info(f"July 2025 breakdown: {dict(result3)}")
                
            except Exception as diag_error:
                logger.error(f"Diagnostic queries failed: {str(diag_error)}")
                # Fallback to basic connection test
                test_query = "SELECT COUNT(*) as total_count FROM client.user_profile WHERE affiliated_partner_id = %s LIMIT 1"
                self.cursor.execute(test_query, (partner_id,))
                test_result = self.cursor.fetchone()
                logger.info(f"Basic test result: {test_result}")
            
            logger.info("=== END DIAGNOSTICS ===")
            
            query = f"""
            SELECT 
                DATE_TRUNC('month', COALESCE(demo_joined_date, real_joined_date))::date as joined_month,
                COUNT(DISTINCT binary_user_id) as demo_count,
                COUNT(DISTINCT binary_user_id) as real_count,
                COUNT(DISTINCT CASE WHEN first_deposit_date IS NOT NULL THEN binary_user_id END) as deposit_count,
                COUNT(DISTINCT CASE WHEN first_trade_date IS NOT NULL THEN binary_user_id END) as traded_count,
                100.0 as demo_to_real_rate,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_deposit_date IS NOT NULL THEN binary_user_id END)::numeric / 
                     NULLIF(COUNT(DISTINCT binary_user_id), 0)) * 100, 2
                ) as demo_to_deposit_rate,
                ROUND(
                    (COUNT(DISTINCT CASE WHEN first_trade_date IS NOT NULL THEN binary_user_id END)::numeric / 
                     NULLIF(COUNT(DISTINCT binary_user_id), 0)) * 100, 2
                ) as demo_to_trade_rate,
                0 as avg_first_deposit_amount
            FROM {table_name}
            WHERE affiliated_partner_id = %s
                AND (demo_joined_date IS NOT NULL OR real_joined_date IS NOT NULL)
                AND is_internal = FALSE
            GROUP BY DATE_TRUNC('month', COALESCE(demo_joined_date, real_joined_date))::date
            ORDER BY joined_month DESC
            LIMIT 12
            """
            
            self.cursor.execute(query, (partner_id,))
            results = self.cursor.fetchall()
            
            # Convert to list of dictionaries and format data
            funnel_data = []
            for row in results:
                row_dict = dict(row)
                # Convert date to string for JSON serialization
                if row_dict['joined_month']:
                    row_dict['joined_month'] = row_dict['joined_month'].strftime('%b %Y')  # Format as "Jan 2025"
                
                # Ensure numeric values are properly formatted
                for key in ['demo_count', 'real_count', 'deposit_count', 'traded_count']:
                    row_dict[key] = int(row_dict[key]) if row_dict[key] is not None else 0
                
                for key in ['demo_to_real_rate', 'demo_to_deposit_rate', 'demo_to_trade_rate', 'avg_first_deposit_amount']:
                    row_dict[key] = float(row_dict[key]) if row_dict[key] is not None else 0.0
                
                funnel_data.append(row_dict)
            
            logger.info(f"Retrieved funnel data for partner {partner_id}: {len(funnel_data)} months")
            return funnel_data
            
        except Exception as e:
            if self.conn:
                self.conn.rollback()  # Rollback transaction on error
            logger.error(f"Error fetching funnel data for partner {partner_id}: {str(e)}")
            raise e
    
    def get_partner_acquisition_summary(self, partner_id: str) -> Dict[str, Any]:
        """
        Get acquisition channel summary for a partner.
        
        Args:
            partner_id (str): The partner ID to get summary for
            
        Returns:
            Dict: Summary of acquisition channels and client sources
        """
        try:
            if not self.conn:
                self.connect()
            
            query = """
            SELECT 
                acquisition_channel,
                utm_source,
                utm_medium,
                COUNT(DISTINCT binary_user_id) as client_count,
                COUNT(DISTINCT CASE WHEN first_deposit_date IS NOT NULL THEN binary_user_id END) as depositing_clients,
                ROUND(AVG(CASE WHEN first_deposit_amount_usd IS NOT NULL THEN first_deposit_amount_usd::numeric ELSE 0 END), 2) as avg_deposit_amount
            FROM client.user_profile
            WHERE affiliated_partner_id = %s
                AND real_joined_date IS NOT NULL
                AND is_internal = FALSE
            GROUP BY acquisition_channel, utm_source, utm_medium
            ORDER BY client_count DESC
            LIMIT 10
            """
            
            self.cursor.execute(query, (partner_id,))
            results = self.cursor.fetchall()
            
            # Convert to list of dictionaries
            summary_data = [dict(row) for row in results]
            
            logger.info(f"Retrieved acquisition summary for partner {partner_id}: {len(summary_data)} channels")
            return {
                'acquisition_channels': summary_data,
                'total_channels': len(summary_data)
            }
            
        except Exception as e:
            if self.conn:
                self.conn.rollback()  # Rollback transaction on error
            logger.error(f"Error fetching acquisition summary for partner {partner_id}: {str(e)}")
            raise e

# Global database instance
db = SupabaseDB() 