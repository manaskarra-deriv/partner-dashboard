import React from 'react';

const Pagination = ({ 
  currentPage, 
  totalPages, 
  totalCount, 
  partnersPerPage, 
  onPageChange,
  showingCount 
}) => {
  const generatePageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 5;
    
    if (totalPages <= maxVisiblePages) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Show smart pagination
      if (currentPage <= 3) {
        // Near the beginning
        for (let i = 1; i <= 4; i++) {
          pages.push(i);
        }
        pages.push('...');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        // Near the end
        pages.push(1);
        pages.push('...');
        for (let i = totalPages - 3; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        // In the middle
        pages.push(1);
        pages.push('...');
        for (let i = currentPage - 1; i <= currentPage + 1; i++) {
          pages.push(i);
        }
        pages.push('...');
        pages.push(totalPages);
      }
    }
    
    return pages;
  };

  if (totalPages <= 1) {
    return (
      <div className="pagination-info">
        <span className="pagination-text">
          Showing {showingCount} of {totalCount} partners
        </span>
      </div>
    );
  }

  const startItem = (currentPage - 1) * partnersPerPage + 1;
  const endItem = Math.min(currentPage * partnersPerPage, totalCount);

  return (
    <div className="pagination-container">
      <div className="pagination-info">
        <span className="pagination-text">
          Showing {startItem}-{endItem} of {totalCount} partners
        </span>
      </div>
      
      <div className="pagination-controls">
        {/* Previous Button */}
        <button
          className={`pagination-btn ${currentPage === 1 ? 'disabled' : ''}`}
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
        >
          ← Previous
        </button>
        
        {/* Page Numbers */}
        <div className="pagination-numbers">
          {generatePageNumbers().map((page, index) => (
            page === '...' ? (
              <span key={`ellipsis-${index}`} className="pagination-ellipsis">
                ...
              </span>
            ) : (
              <button
                key={page}
                className={`pagination-number ${currentPage === page ? 'active' : ''}`}
                onClick={() => onPageChange(page)}
              >
                {page}
              </button>
            )
          ))}
        </div>
        
        {/* Next Button */}
        <button
          className={`pagination-btn ${currentPage === totalPages ? 'disabled' : ''}`}
          disabled={currentPage === totalPages}
          onClick={() => onPageChange(currentPage + 1)}
        >
          Next →
        </button>
      </div>
    </div>
  );
};

export default Pagination; 