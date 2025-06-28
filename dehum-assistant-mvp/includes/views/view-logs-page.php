<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}
?>
<div class="wrap">
    <h1>💬 <?php _e('Chat Conversations', 'dehum-assistant-mvp'); ?></h1>
    
    <!-- Settings Form -->
    <form method="post" action="options.php" class="dehum-admin-settings">
        <?php settings_fields('dehum_mvp_options_group'); ?>
        <h2><?php _e('Settings', 'dehum-assistant-mvp'); ?></h2>
        <table class="form-table">
            <tr valign="top">
                <th scope="row"><label for="dehum_mvp_n8n_webhook_url"><?php _e('n8n Webhook URL', 'dehum-assistant-mvp'); ?></label></th>
                <td>
                    <input type="url" id="dehum_mvp_n8n_webhook_url" name="dehum_mvp_n8n_webhook_url" value="<?php echo esc_attr(get_option('dehum_mvp_n8n_webhook_url')); ?>" class="regular-text" placeholder="https://your-n8n-instance.com/webhook/..." />
                    <p class="description"><?php _e('Enter the full webhook URL for your n8n workflow.', 'dehum-assistant-mvp'); ?></p>
                </td>
            </tr>
            <tr valign="top">
                <th scope="row"><label for="dehum_mvp_n8n_webhook_user"><?php _e('n8n Webhook Username', 'dehum-assistant-mvp'); ?></label></th>
                <td>
                    <input type="text" id="dehum_mvp_n8n_webhook_user" name="dehum_mvp_n8n_webhook_user" value="<?php echo esc_attr(get_option('dehum_mvp_n8n_webhook_user')); ?>" class="regular-text" placeholder="<?php esc_attr_e('Username', 'dehum-assistant-mvp'); ?>" />
                    <p class="description"><?php _e('The Basic Auth username for your n8n webhook.', 'dehum-assistant-mvp'); ?></p>
                </td>
            </tr>
            <tr valign="top">
                <th scope="row"><label for="dehum_mvp_n8n_webhook_pass"><?php _e('n8n Webhook Password', 'dehum-assistant-mvp'); ?></label></th>
                <td>
                    <input type="password" id="dehum_mvp_n8n_webhook_pass" name="dehum_mvp_n8n_webhook_pass" value="<?php echo esc_attr(get_option('dehum_mvp_n8n_webhook_pass')); ?>" class="regular-text" placeholder="<?php esc_attr_e('Password', 'dehum-assistant-mvp'); ?>" />
                    <p class="description"><?php _e('The Basic Auth password for your n8n webhook.', 'dehum-assistant-mvp'); ?></p>
                </td>
            </tr>
        </table>
        <?php submit_button(); ?>
    </form>
    
    <!-- Stats Summary -->
    <div class="dehum-stats-summary">
        <div class="dehum-stats-grid">
            <div class="dehum-stat-item large">
                <div class="stat-number"><?php echo number_format($all_stats['total_sessions']); ?></div>
                <div class="stat-label"><?php _e('Total Sessions', 'dehum-assistant-mvp'); ?></div>
            </div>
            <div class="dehum-stat-item large">
                <div class="stat-number"><?php echo number_format($all_stats['total_messages']); ?></div>
                <div class="stat-label"><?php _e('Total Messages', 'dehum-assistant-mvp'); ?></div>
            </div>
            <div class="dehum-stat-item large">
                <div class="stat-number"><?php echo $all_stats['total_sessions'] > 0 ? round($all_stats['total_messages'] / $all_stats['total_sessions'], 1) : 0; ?></div>
                <div class="stat-label"><?php _e('Avg per Session', 'dehum-assistant-mvp'); ?></div>
            </div>
            <?php if ($total_sessions != $all_stats['total_sessions']): ?>
            <div class="dehum-stat-item medium filtered">
                <div class="stat-number"><?php echo number_format($total_sessions); ?></div>
                <div class="stat-label"><?php _e('Filtered Results', 'dehum-assistant-mvp'); ?></div>
            </div>
            <?php endif; ?>
        </div>
    </div>

    <!-- Filters and Actions -->
    <div class="dehum-filters">
        <form method="GET" action="">
            <input type="hidden" name="page" value="dehum-mvp-logs">
            
            <div class="dehum-filters-grid">
                <!-- Search -->
                <div class="dehum-filter-field">
                    <label><?php _e('Search Conversations', 'dehum-assistant-mvp'); ?></label>
                    <input type="text" name="search" value="<?php echo esc_attr($filters['search']); ?>" placeholder="<?php esc_attr_e('Search messages...', 'dehum-assistant-mvp'); ?>">
                </div>
                
                <!-- Date Filter -->
                <div class="dehum-filter-field">
                    <label><?php _e('Date Range', 'dehum-assistant-mvp'); ?></label>
                    <select name="date_filter" onchange="this.form.submit()">
                        <option value=""><?php _e('All Time', 'dehum-assistant-mvp'); ?></option>
                        <option value="7_days" <?php selected($filters['date_filter'], '7_days'); ?>><?php _e('Last 7 Days', 'dehum-assistant-mvp'); ?></option>
                        <option value="30_days" <?php selected($filters['date_filter'], '30_days'); ?>><?php _e('Last 30 Days', 'dehum-assistant-mvp'); ?></option>
                        <option value="90_days" <?php selected($filters['date_filter'], '90_days'); ?>><?php _e('Last 90 Days', 'dehum-assistant-mvp'); ?></option>
                    </select>
                </div>
                
                <!-- Per Page -->
                <div class="dehum-filter-field">
                    <label><?php _e('Per Page', 'dehum-assistant-mvp'); ?></label>
                    <select name="per_page" onchange="this.form.submit()">
                        <option value="10" <?php selected($filters['per_page'], 10); ?>>10</option>
                        <option value="20" <?php selected($filters['per_page'], 20); ?>>20</option>
                        <option value="50" <?php selected($filters['per_page'], 50); ?>>50</option>
                        <option value="100" <?php selected($filters['per_page'], 100); ?>>100</option>
                    </select>
                </div>
                
                <!-- Filter Button -->
                <div class="dehum-filter-field">
                    <button type="submit" class="button button-primary"><?php _e('Filter', 'dehum-assistant-mvp'); ?></button>
                </div>
            </div>
        </form>
        
        <!-- Actions -->
        <div class="dehum-filter-actions">
            <div>
                <?php if ($total_sessions > 0): ?>
                    <a href="<?php echo wp_nonce_url(add_query_arg(['action' => 'export'] + $_GET), 'dehum_export', 'export_nonce'); ?>" class="button">📊 <?php _e('Export CSV', 'dehum-assistant-mvp'); ?></a>
                <?php endif; ?>
            </div>
            
            <div class="dehum-bulk-actions">
                <form method="POST" onsubmit="return confirm('<?php esc_attr_e('Are you sure?', 'dehum-assistant-mvp'); ?>');">
                    <?php wp_nonce_field('dehum_bulk_actions', 'bulk_nonce'); ?>
                    <input type="hidden" name="bulk_action" value="delete_old">
                    <button type="submit" class="button button-secondary">🗑️ <?php _e('Delete Old (90+ days)', 'dehum-assistant-mvp'); ?></button>
                </form>
            </div>
        </div>
    </div>

    <?php if (empty($sessions)): ?>
        <div class="dehum-empty-state">
            <h3><?php _e('No conversations found', 'dehum-assistant-mvp'); ?></h3>
            <p><?php _e('No conversations match your current filters. Try a different search or date range.', 'dehum-assistant-mvp'); ?></p>
        </div>
    <?php else: ?>
        
        <!-- Conversations List -->
        <div id="conversations-list">
            <?php foreach ($sessions as $session): ?>
                <div class="conversation-card" data-session="<?php echo esc_attr($session->session_id); ?>">
                    <div class="card-header">
                        <div class="conversation-info">
                            <div class="conversation-preview"><?php echo esc_html(wp_trim_words($session->first_question, 12)); ?></div>
                            <div class="conversation-meta">
                                <span><?php echo intval($session->message_count); ?> messages</span>
                                <span><?php echo human_time_diff(strtotime($session->last_message), current_time('timestamp')); ?> ago</span>
                                <span><?php echo esc_html($session->user_ip); ?></span>
                            </div>
                        </div>
                        <div class="expand-icon"><span class="dashicons dashicons-arrow-down-alt2"></span></div>
                    </div>
                    <div class="card-content" id="content-<?php echo esc_attr($session->session_id); ?>" style="display: none;">
                        <div class="loading-state">Loading...</div>
                    </div>
                </div>
            <?php endforeach; ?>
        </div>
        
        <!-- Pagination -->
        <div class="dehum-pagination">
            <?php
            // Pagination logic here
            ?>
        </div>
        
    <?php endif; ?>
</div> 