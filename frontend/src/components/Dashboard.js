import React from 'react';
import PartnerOverview from './PartnerOverview';
import TierAnalytics from './TierAnalytics';
import PartnerTable from './PartnerTable';
import PartnerFilters from './PartnerFilters';
import AICopilot from './AICopilot';

const Dashboard = ({ 
  overview, 
  tierAnalytics,
  partners, 
  filters, 
  activeFilters, 
  loading, 
  onFilterChange, 
  onPartnerSelect,
  formatCurrency,
  formatNumber,
  formatVolume,
  getTierColor,
  sortField,
  sortDirection,
  onSortChange,
  // Pagination props
  currentPage,
  totalPages,
  totalCount,
  partnersPerPage,
  onPageChange
}) => {
  return (
    <>
      {/* Overview Section */}
      {overview && (
        <section className="overview-section">
          <div className="section-header">
            <h2 className="heading-lg">Partner Overview</h2>
            <p className="text-secondary">Real-time partner performance metrics</p>
          </div>
          <PartnerOverview 
            overview={overview} 
            formatCurrency={formatCurrency}
            formatNumber={formatNumber}
          />
        </section>
      )}

      {/* Tier Analytics Section */}
      <section className="tier-analytics-section">
        <TierAnalytics 
          analytics={tierAnalytics}
          formatCurrency={formatCurrency}
          formatNumber={formatNumber}
          formatVolume={formatVolume}
          mainLoading={loading}
        />
      </section>

      {/* Filters and Table Section */}
      <section className="partners-section">
        <div className="section-header">
          <h2 className="heading-lg">Partner Management</h2>
          <p className="text-secondary">Filter and analyze partner performance</p>
        </div>

        <div className="filters-container">
          <PartnerFilters
            filters={filters}
            activeFilters={activeFilters}
            onFilterChange={onFilterChange}
          />
        </div>

        <div className="table-container">
          <PartnerTable
            partners={partners}
            loading={loading}
            onPartnerSelect={onPartnerSelect}
            formatCurrency={formatCurrency}
            formatNumber={formatNumber}
            formatVolume={formatVolume}
            getTierColor={getTierColor}
            sortField={sortField}
            sortDirection={sortDirection}
            onSortChange={onSortChange}
            // Pagination props
            currentPage={currentPage}
            totalPages={totalPages}
            totalCount={totalCount}
            partnersPerPage={partnersPerPage}
            onPageChange={onPageChange}
            mainLoading={loading}
          />
        </div>
      </section>

      {/* AI Copilot for Dashboard Insights */}
      <AICopilot 
        context="dashboard"
        data={{
          overview,
          partners: partners.slice(0, 10), // Top 10 partners for analysis
          activeFilters
        }}
      />
    </>
  );
};

export default Dashboard; 