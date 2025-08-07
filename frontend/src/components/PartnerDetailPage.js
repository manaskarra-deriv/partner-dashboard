import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import PartnerDetail from './PartnerDetail';
import LoadingScreen from './LoadingScreen';

const PartnerDetailPage = ({ formatCurrency, formatNumber, formatVolume, getTierColor, onBack }) => {
  const { partnerId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [partner, setPartner] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPartnerDetail = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_BASE_URL}/api/partners/${partnerId}`);
        setPartner(response.data);
      } catch (err) {
        console.error('Error fetching partner detail:', err);
        setError('Failed to load partner details');
      } finally {
        setLoading(false);
      }
    };

    if (partnerId) {
      fetchPartnerDetail();
    }
  }, [partnerId]);

  const handleBackToDashboard = () => {
    if (onBack) {
      onBack();
    } else {
      // Fallback if onBack prop is not provided
      const savedState = location.state;
      if (savedState) {
        navigate('/', { state: savedState });
      } else {
        navigate('/');
      }
    }
  };

  if (loading) {
    return <LoadingScreen fullscreen hideText />;
  }

  if (error) {
    return (
      <div className="error-state">
        <h3>Error</h3>
        <p>{error}</p>
        <button onClick={handleBackToDashboard} className="btn-primary">
          Back to Dashboard
        </button>
      </div>
    );
  }

  if (!partner) {
    return (
      <div className="empty-state">
        <h3>Partner Not Found</h3>
        <p>The requested partner could not be found.</p>
        <button onClick={handleBackToDashboard} className="btn-primary">
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <>
      <PartnerDetail 
        partner={partner}
        formatCurrency={formatCurrency}
        formatNumber={formatNumber}
        formatVolume={formatVolume}
        getTierColor={getTierColor}
        onBack={handleBackToDashboard}
      />
    </>
  );
};

export default PartnerDetailPage; 