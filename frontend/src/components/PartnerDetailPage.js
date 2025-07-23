import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import PartnerDetail from './PartnerDetail';
import AICopilot from './AICopilot';
import LoadingScreen from './LoadingScreen';

const PartnerDetailPage = ({ formatCurrency, formatNumber, formatVolume, getTierColor }) => {
  const { partnerId } = useParams();
  const navigate = useNavigate();
  const [partner, setPartner] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPartnerDetail = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/partners/${partnerId}`);
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
    navigate('/');
  };

  if (loading) {
    return <LoadingScreen fullscreen />;
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
      
      {/* AI Copilot for Partner Detail Insights */}
      {partner && (
        <AICopilot 
          context="partner_detail"
          data={{
            partner_info: partner.partner_info,
            monthly_performance: partner.monthly_performance,
            current_month: partner.current_month
          }}
        />
      )}
    </>
  );
};

export default PartnerDetailPage; 