import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any
from datetime import datetime
import time
import threading

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
        self.connection_pool = None
        self.lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool with retry logic"""
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Close existing pool if it exists
                if self.connection_pool:
                    try:
                        self.connection_pool.closeall()
                    except Exception:
                        pass
                    self.connection_pool = None
                
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,  # Reduced minimum connections
                    maxconn=8,   # Reduced maximum connections for better stability
                    **self.db_params,
                    # Enhanced connection parameters
                    connect_timeout=30,
                    keepalives=1,
                    keepalives_idle=600,  # 10 minutes (longer than 5 min timeout)
                    keepalives_interval=30,
                    keepalives_count=3,
                    application_name='PDash_Backend',
                    # Add statement timeout to prevent hanging queries
                    options='-c statement_timeout=60000'  # 60 seconds
                )
                logger.info("Successfully initialized connection pool to Supabase database")
                return
            except Exception as e:
                logger.error(f"Failed to initialize connection pool (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise e
    
    def get_connection(self):
        """Get a connection from the pool with automatic retry"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                with self.lock:
                    if self.connection_pool is None:
                        logger.warning("Connection pool is None, reinitializing...")
                        self._initialize_pool()
                    
                    conn = self.connection_pool.getconn()
                    
                    # Test the connection
                    if conn.closed != 0:
                        logger.warning("Retrieved closed connection, getting new one...")
                        self.connection_pool.putconn(conn, close=True)
                        conn = self.connection_pool.getconn()
                    
                    # Test with a simple query
                    with conn.cursor() as test_cursor:
                        test_cursor.execute("SELECT 1")
                        test_cursor.fetchone()
                    
                    return conn
                    
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    # Try to reinitialize pool if connection fails
                    try:
                        with self.lock:
                            if self.connection_pool:
                                self.connection_pool.closeall()
                            self._initialize_pool()
                    except Exception:
                        pass
                    time.sleep(retry_delay)
                else:
                    raise e
    
    def return_connection(self, conn, close=False):
        """Return a connection to the pool"""
        if not conn:
            return
            
        try:
            with self.lock:
                if self.connection_pool and conn:
                    # Check if connection is still valid before returning
                    if conn.closed == 0 and not close:
                        self.connection_pool.putconn(conn, close=False)
                    else:
                        # Close invalid connections
                        try:
                            conn.close()
                        except Exception:
                            pass
                        self.connection_pool.putconn(conn, close=True)
        except Exception as e:
            # If we can't return to pool, just close the connection
            try:
                if conn and conn.closed == 0:
                    conn.close()
            except Exception:
                pass
            logger.warning(f"Could not return connection to pool (closed it instead): {str(e)}")
    
    def execute_query(self, query, params=None, fetch_all=True):
        """Execute a query with automatic connection management and retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            conn = None
            try:
                conn = self.get_connection()
                
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Set a statement timeout for this specific query
                    cursor.execute("SET statement_timeout = '60s'")
                    cursor.execute(query, params)
                    
                    if fetch_all:
                        results = cursor.fetchall()
                        # Convert to list of dictionaries for JSON serialization
                        return [dict(row) for row in results]
                    else:
                        result = cursor.fetchone()
                        return dict(result) if result else None
                        
            except Exception as e:
                error_msg = str(e).lower()
                
                # Enhanced error detection for various timeout and connection issues
                is_connection_error = any(keyword in error_msg for keyword in [
                    'connection', 'timeout', 'broken', 'closed', 'lost', 
                    'network', 'server closed', 'ssl', 'canceling statement',
                    'statement timeout', 'query cancelled', 'connection lost'
                ])
                
                if is_connection_error and attempt < max_retries - 1:
                    logger.warning(f"Connection/timeout error on attempt {attempt + 1}: {str(e)}")
                    if conn:
                        self.return_connection(conn, close=True)
                        conn = None
                    
                    # Exponential backoff with jitter
                    delay = retry_delay * (attempt + 1) + (attempt * 0.5)
                    time.sleep(delay)
                    continue
                
                # For non-connection errors or final attempt
                if attempt == max_retries - 1:
                    logger.error(f"Query execution failed after {max_retries} attempts: {str(e)}")
                else:
                    logger.error(f"Query execution failed (non-retryable): {str(e)}")
                
                # Return connection before raising error
                if conn:
                    self.return_connection(conn, close=is_connection_error)
                    conn = None
                
                raise e
            
            finally:
                # Ensure connection is always returned
                if conn:
                    self.return_connection(conn)
    
    def disconnect(self):
        """Close all connections in the pool"""
        try:
            with self.lock:
                if self.connection_pool:
                    self.connection_pool.closeall()
                    self.connection_pool = None
                logger.info("All database connections closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {str(e)}")
    
    def get_partner_funnel_data(self, partner_id: str) -> List[Dict[str, Any]]:
        """
        Get monthly funnel performance data for a specific partner with Demo, Real, Deposit, Traded stages.
        
        Args:
            partner_id (str): The partner ID to get funnel data for
            
        Returns:
            List[Dict]: Monthly funnel data with demo, real, deposit, traded counts and conversion rates
        """
        try:
            table_name = "client.user_profile"
            
            query = f"""
            SELECT 
                DATE_TRUNC('month', real_joined_date)::date as joined_month,
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
                ROUND(
                    AVG(CASE WHEN first_deposit_amount_usd IS NOT NULL THEN first_deposit_amount_usd::numeric ELSE 0 END), 2
                ) as avg_first_deposit_amount
            FROM {table_name}
            WHERE affiliated_partner_id = %s
                AND real_joined_date IS NOT NULL
                AND is_internal = FALSE
            GROUP BY DATE_TRUNC('month', real_joined_date)::date
            ORDER BY joined_month DESC
            LIMIT 12
            """
            
            results = self.execute_query(query, (partner_id,))
            
            # Format data for frontend
            funnel_data = []
            for row in results:
                # Convert date to string for JSON serialization
                if row['joined_month']:
                    row['joined_month'] = row['joined_month'].strftime('%b %Y')  # Format as "Jan 2025"
                
                # Ensure numeric values are properly formatted
                for key in ['demo_count', 'real_count', 'deposit_count', 'traded_count']:
                    row[key] = int(row[key]) if row[key] is not None else 0
                
                for key in ['demo_to_real_rate', 'demo_to_deposit_rate', 'demo_to_trade_rate', 'avg_first_deposit_amount']:
                    row[key] = float(row[key]) if row[key] is not None else 0.0
                
                funnel_data.append(row)
            
            logger.info(f"Retrieved funnel data for partner {partner_id}: {len(funnel_data)} months")
            return funnel_data
            
        except Exception as e:
            logger.error(f"Error fetching funnel data for partner {partner_id}: {str(e)}")
            # Return empty list instead of raising to prevent frontend hanging
            return []
    
    def get_partner_acquisition_summary(self, partner_id: str) -> Dict[str, Any]:
        """
        Get acquisition channel summary for a partner.
        
        Args:
            partner_id (str): The partner ID to get summary for
            
        Returns:
            Dict: Summary of acquisition channels and client sources
        """
        try:
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
            
            results = self.execute_query(query, (partner_id,))
            
            logger.info(f"Retrieved acquisition summary for partner {partner_id}: {len(results)} channels")
            return {
                'acquisition_channels': results,
                'total_channels': len(results)
            }
            
        except Exception as e:
            logger.error(f"Error fetching acquisition summary for partner {partner_id}: {str(e)}")
            return {'acquisition_channels': [], 'total_channels': 0}

    def get_partner_regions_mapping(self) -> Dict[str, str]:
        """
        Get mapping of partner_id to partner_region from the partner.partner_info table.
        
        Returns:
            Dict: Mapping of partner_id to partner_region (GP regions)
        """
        try:
            query = """
            SELECT 
                partner_id,
                partner_region
            FROM partner.partner_info
            WHERE partner_region IS NOT NULL
            """
            
            results = self.execute_query(query)
            
            # Convert to dictionary mapping
            partner_regions = {str(row['partner_id']): row['partner_region'] for row in results}
            
            logger.info(f"Retrieved GP region mapping for {len(partner_regions)} partners")
            return partner_regions
            
        except Exception as e:
            logger.error(f"Error fetching partner regions mapping: {str(e)}")
            return {}  # Return empty dict on error instead of raising

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database connection
        
        Returns:
            Dict: Health status information
        """
        try:
            start_time = time.time()
            result = self.execute_query("SELECT 1 as health_check, NOW() as server_time", fetch_all=False)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Get pool status safely
            pool_status = {'available_connections': 0, 'used_connections': 0}
            try:
                if self.connection_pool:
                    # For psycopg2 ThreadedConnectionPool, we need to check differently
                    with self.lock:
                        # Get pool stats indirectly by checking the internal attributes
                        total_connections = self.connection_pool.maxconn
                        # The pool doesn't expose used/available directly, so we provide basic info
                        pool_status = {
                            'total_connections': total_connections,
                            'min_connections': self.connection_pool.minconn,
                            'max_connections': self.connection_pool.maxconn,
                            'pool_initialized': True,
                            'keepalive_settings': {
                                'keepalives_idle': '600s',
                                'statement_timeout': '60s'
                            }
                        }
            except Exception as pool_error:
                logger.warning(f"Could not get detailed pool status: {str(pool_error)}")
                pool_status = {'pool_initialized': bool(self.connection_pool)}
            
            return {
                'status': 'healthy',
                'response_time_ms': round(response_time, 2),
                'server_time': result['server_time'].isoformat() if result and result['server_time'] else None,
                'pool_status': pool_status
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'response_time_ms': None,
                'server_time': None,
                'pool_status': {
                    'pool_initialized': False,
                    'error': 'Health check failed'
                }
            }

# Global database instance
db = SupabaseDB() 