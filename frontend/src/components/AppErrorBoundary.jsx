import React from 'react';

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    console.error('Mini App render error:', error);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const isAdmin = this.props.admin;
    return (
      <main
        role="alert"
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          padding: 24,
          background: isAdmin ? '#f1f3ef' : '#fbfcf9',
          color: '#172924',
          fontFamily: "'Plus Jakarta Sans', 'Noto Sans Ethiopic', system-ui, sans-serif",
          textAlign: 'center',
        }}
      >
        <section style={{ maxWidth: 420 }}>
          <h1 style={{ margin: '0 0 10px', fontSize: 22 }}>
            {isAdmin ? 'Admin app unavailable' : 'Something went wrong'}
          </h1>
          <p style={{ margin: '0 0 18px', color: '#78847c', lineHeight: 1.6, fontSize: 14 }}>
            Please reopen the Mini App. If the problem continues, contact support.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              border: 0,
              borderRadius: 10,
              padding: '11px 18px',
              background: '#183b34',
              color: '#fbfcf9',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Reload
          </button>
        </section>
      </main>
    );
  }
}
