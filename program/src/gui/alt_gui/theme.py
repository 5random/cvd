from nicegui import ui


def setup_global_styles():
    """Setup CSS styles matching the main application"""
    ui.add_head_html("""
            <style>
                .cvd-header {
                    background: linear-gradient(90deg, #1976d2, #1565c0);
                }
                .cvd-card {
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    padding: 16px;
                }
                .cvd-sensor-value {
                    font-size: 1.5rem;
                    font-weight: bold;
                }
                .placeholder-content {
                    background: #f5f5f5;
                    border: 2px dashed #ccc;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #666;
                    min-height: 200px;
                }
                /* Motion status indicators */
                .motion-detected {
                    color: #ff9800;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                /* Card improvements */
                .cvd-card .q-expansion-item {
                    border: none;
                    box-shadow: none;
                }
                .cvd-card .q-expansion-item__container {
                    padding: 0;
                }
                /* Masonry layout improvements */
                .masonry-grid {
                    display: grid !important;
                    grid-template-columns: 2fr 1fr;
                    grid-template-rows: auto auto;
                    gap: 1rem;
                    grid-template-areas:
                        "camera motion"
                        "experiment alerts";
                }
                /* Responsive adjustments */
                @media (max-width: 1024px) {
                    .masonry-grid {
                        grid-template-columns: 1fr !important;
                        grid-template-areas:
                            "camera"
                            "motion"
                            "experiment"
                            "alerts" !important;
                    }
                }
            </style>
    """)
