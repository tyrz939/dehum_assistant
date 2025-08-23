<?php
// Prevent direct access
if (!defined('ABSPATH')) exit;

// Settings Form
settings_errors(); ?>
<form method="post" action="options.php" class="dehum-admin-settings">
    <?php
    settings_fields('dehum_mvp_options_group');
    do_settings_sections('dehum-mvp-logs');
    submit_button();
    ?>
</form>

<!-- Stats Summary -->
<div class="dehum-stats-summary">
    <div class="dehum-stats-grid">
        <div class="dehum-stat-item large">
            <div class="stat-number"><?php echo number_format($stats['total_sessions']); ?></div>
            <div class="stat-label"><?php _e('Total Sessions', 'dehum-assistant-mvp'); ?></div>
        </div>
        <div class="dehum-stat-item large">
            <div class="stat-number"><?php echo number_format($stats['total_messages']); ?></div>
            <div class="stat-label"><?php _e('Total Messages', 'dehum-assistant-mvp'); ?></div>
        </div>
        <div class="dehum-stat-item large">
            <div class="stat-number"><?php echo $stats['total_sessions'] > 0 ? round($stats['total_messages'] / $stats['total_sessions'], 1) : 0; ?></div>
            <div class="stat-label"><?php _e('Avg per Session', 'dehum-assistant-mvp'); ?></div>
        </div>
        <?php if ($total != $stats['total_sessions']): ?>
        <div class="dehum-stat-item medium filtered">
            <div class="stat-number"><?php echo number_format($total); ?></div>
            <div class="stat-label"><?php _e('Filtered Results', 'dehum-assistant-mvp'); ?></div>
        </div>
        <?php endif; ?>
    </div>
</div>

<!-- Filters Form -->
<div class="dehum-filters">
    <form method="GET" action="">
        <input type="hidden" name="page" value="dehum-mvp-logs">
        <div class="dehum-filters-grid">
            <div class="dehum-filter-field">
                <label for="search"><?php _e('Search', 'dehum-assistant-mvp'); ?></label>
                <input type="text" id="search" name="search" value="<?php echo esc_attr($filters['search']); ?>" placeholder="<?php esc_attr_e('Search messages or ID...', 'dehum-assistant-mvp'); ?>">
            </div>
            <div class="dehum-filter-field">
                <label for="date_filter"><?php _e('Date Range', 'dehum-assistant-mvp'); ?></label>
                <select id="date_filter" name="date_filter" onchange="toggleCustomDates(this.value)">
                    <option value=""><?php _e('All Time', 'dehum-assistant-mvp'); ?></option>
                    <option value="7_days" <?php selected($filters['date_filter'], '7_days'); ?>><?php _e('Last 7 Days', 'dehum-assistant-mvp'); ?></option>
                    <option value="30_days" <?php selected($filters['date_filter'], '30_days'); ?>><?php _e('Last 30 Days', 'dehum-assistant-mvp'); ?></option>
                    <option value="90_days" <?php selected($filters['date_filter'], '90_days'); ?>><?php _e('Last 90 Days', 'dehum-assistant-mvp'); ?></option>
                    <option value="custom" <?php selected($filters['date_filter'], 'custom'); ?>><?php _e('Custom', 'dehum-assistant-mvp'); ?></option>
                </select>
            </div>
            <div class="dehum-filter-field">
                <label for="ip_filter"><?php _e('IP Address', 'dehum-assistant-mvp'); ?></label>
                <input type="text" id="ip_filter" name="ip_filter" value="<?php echo esc_attr($filters['ip_filter']); ?>" placeholder="<?php esc_attr_e('Filter by IP...', 'dehum-assistant-mvp'); ?>">
            </div>
            <div class="dehum-filter-field">
                <label for="per_page"><?php _e('Per Page', 'dehum-assistant-mvp'); ?></label>
                <select id="per_page" name="per_page" onchange="this.form.submit()">
                    <option value="10" <?php selected($filters['per_page'], 10); ?>>10</option>
                    <option value="20" <?php selected($filters['per_page'], 20); ?>>20</option>
                    <option value="50" <?php selected($filters['per_page'], 50); ?>>50</option>
                    <option value="100" <?php selected($filters['per_page'], 100); ?>>100</option>
                </select>
            </div>
            <div class="dehum-filter-field">
                <button type="submit" class="button button-primary"><?php _e('Filter', 'dehum-assistant-mvp'); ?></button>
                <?php if ($filters['search'] || $filters['date_filter'] || $filters['ip_filter']): ?>
                    <a href="<?php echo admin_url('tools.php?page=dehum-mvp-logs'); ?>" class="button"><?php _e('Clear', 'dehum-assistant-mvp'); ?></a>
                <?php endif; ?>
            </div>
        </div>
        
        <!-- Custom Dates -->
        <div id="custom-dates" class="dehum-custom-dates" style="display: <?php echo $filters['date_filter'] === 'custom' ? 'block' : 'none'; ?>;">
            <div class="dehum-custom-dates-grid">
                <div class="dehum-filter-field">
                    <label for="custom_start"><?php _e('Start Date', 'dehum-assistant-mvp'); ?></label>
                    <input type="date" id="custom_start" name="custom_start" value="<?php echo esc_attr($filters['custom_start']); ?>">
                </div>
                <div class="dehum-filter-field">
                    <label for="custom_end"><?php _e('End Date', 'dehum-assistant-mvp'); ?></label>
                    <input type="date" id="custom_end" name="custom_end" value="<?php echo esc_attr($filters['custom_end']); ?>">
                </div>
            </div>
        </div>
    </form>
    
    <!-- Filter Actions -->
    <div class="dehum-filter-actions">
        <div>
            <?php if ($total > 0): ?>
                <a href="<?php echo wp_nonce_url(add_query_arg(['action' => 'export'] + $_GET), DEHUM_MVP_EXPORT_NONCE, 'export_nonce'); ?>" class="button">📊 <?php _e('Export CSV', 'dehum-assistant-mvp'); ?></a>
            <?php endif; ?>
        </div>
        <div class="quick-delete-actions">
            <form method="POST" style="display: inline;" onsubmit="return confirm('Delete old conversations?');">
                <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                <input type="hidden" name="bulk_action" value="delete_old">
                <button type="submit" class="button button-secondary">🗑️ <?php printf(__('Delete Old (%d+ days)', 'dehum-assistant-mvp'), DEHUM_MVP_OLD_CONVERSATIONS_DAYS); ?></button>
            </form>
            <button type="button" class="button" onclick="toggleAdvancedDelete()">More Options</button>
        </div>
    </div>
    
    <!-- Advanced Delete -->
    <div id="advanced-delete" class="dehum-advanced-delete" style="display: none;">
        <h3>Advanced Delete</h3>
        <div class="advanced-delete-grid">
            <div class="delete-option">
                <h4>By Date Range</h4>
                <form method="POST" onsubmit="return confirm('Delete in range?');">
                    <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                    <input type="hidden" name="bulk_action" value="delete_by_date">
                    <div class="date-inputs">
                        <input type="date" name="delete_start_date" required>
                        to
                        <input type="date" name="delete_end_date" required>
                    </div>
                    <button type="submit" class="button button-secondary">Delete</button>
                </form>
            </div>
            <div class="delete-option">
                <h4>By IP</h4>
                <form method="POST" onsubmit="return confirm('Delete by IP?');">
                    <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                    <input type="hidden" name="bulk_action" value="delete_by_ip">
                    <input type="text" name="delete_ip" placeholder="192.168.1.1" required>
                    <button type="submit" class="button button-secondary">Delete</button>
                </form>
            </div>
        </div>
    </div>
</div>

<?php if (empty($sessions)): ?>
    <div class="dehum-empty-state">
        <h3>No conversations</h3>
        <p>Adjust filters or check back later.</p>
    </div>
<?php else: ?>
    <!-- Results Header -->
    <div class="dehum-results-header">
        <div class="results-info">
            <?php 
            $start = (($current_page - 1) * $filters['per_page']) + 1;
            $end = min($current_page * $filters['per_page'], $total);
            printf(__('Showing %d-%d of %d', 'dehum-assistant-mvp'), $start, $end, $total);
            ?>
        </div>
        <div class="bulk-actions-top">
            <label><input type="checkbox" id="master-select-all" onclick="selectAllConversations(this.checked)"> Select All</label>
            <form method="POST" id="bulk-delete-form">
                <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                <input type="hidden" name="bulk_action" value="delete_selected">
                <select id="bulk-action-selector">
                    <option value="">Bulk Actions</option>
                    <option value="delete">Delete Selected</option>
                </select>
                <button type="submit" class="button" disabled id="bulk-apply-btn">Apply</button>
            </form>
        </div>
    </div>

    <!-- Conversations List -->
    <div id="conversations-list">
        <?php foreach ($sessions as $session): ?>
            <div class="conversation-card" data-session="<?php echo esc_attr($session->session_id); ?>">
                <div class="card-header">
                    <input type="checkbox" name="selected_sessions[]" value="<?php echo esc_attr($session->session_id); ?>" class="session-checkbox">
                    <div class="conversation-info">
                        <div class="conversation-preview"><?php echo esc_html(wp_trim_words($session->first_question, 12)); ?></div>
                        <div class="conversation-meta">
                            <span class="message-count"><?php echo intval($session->message_count); ?> exchanges</span>
                            <span><?php echo human_time_diff(strtotime($session->last_message)); ?> ago</span>
                            <span class="user-ip"><?php echo esc_html($session->user_ip); ?></span>
                        </div>
                    </div>
                    <div class="conversation-actions">
                        <button class="delete-session-btn" data-session="<?php echo esc_attr($session->session_id); ?>" title="Delete this conversation" aria-label="Delete conversation">🗑️</button>
                        <div class="expand-icon" role="button" tabindex="0" aria-label="Toggle conversation details"><span class="dashicons dashicons-arrow-down-alt2"></span></div>
                    </div>
                </div>
                <div class="card-content" id="content-<?php echo esc_attr($session->session_id); ?>" style="display: none;">
                    <div class="loading-state">Loading...</div>
                </div>
            </div>
        <?php endforeach; ?>
    </div>

    <!-- Pagination -->
    <?php if ($total_pages > 1): ?>
    <div class="dehum-pagination">
        <?php echo $pagination; ?>
    </div>
    <?php endif; ?>
<?php endif; ?> 