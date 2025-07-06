<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Display admin messages
$success_message = get_transient('dehum_admin_success');
$error_message = get_transient('dehum_admin_error');
if ($success_message) {
    echo '<div class="notice notice-success is-dismissible"><p>' . esc_html($success_message) . '</p></div>';
    delete_transient('dehum_admin_success');
}
if ($error_message) {
    echo '<div class="notice notice-error is-dismissible"><p>' . esc_html($error_message) . '</p></div>';
    delete_transient('dehum_admin_error');
}

// Calculate pagination
$total_pages = ceil($total_sessions / $filters['per_page']);
$current_page = $filters['paged'];
?>
<div class="wrap">
    <h1>💬 <?php _e('Chat Conversations', 'dehum-assistant-mvp'); ?></h1>
    
    <!-- Settings Form -->
    <form method="post" action="options.php" class="dehum-admin-settings">
        <?php settings_fields('dehum_mvp_options_group'); ?>
        <h2><?php _e('AI Service Settings', 'dehum-assistant-mvp'); ?></h2>
        
        <!-- Python AI Service Settings (Primary) -->
        <table class="form-table">
            <tr valign="top">
                <th scope="row"><label for="dehum_mvp_ai_service_url"><?php _e('Python AI Service URL', 'dehum-assistant-mvp'); ?></label></th>
                <td>
                    <input type="url" id="dehum_mvp_ai_service_url" name="dehum_mvp_ai_service_url" value="<?php echo esc_attr(get_option('dehum_mvp_ai_service_url')); ?>" class="regular-text" placeholder="http://localhost:8000" />
                    <p class="description">
                        <?php _e('Enter the URL of your Python AI service (without /chat endpoint).', 'dehum-assistant-mvp'); ?>
                        <br><strong><?php _e('Recommended:', 'dehum-assistant-mvp'); ?></strong> <code>http://localhost:8000</code> <?php _e('for local development', 'dehum-assistant-mvp'); ?>
                    </p>
                </td>
            </tr>
            <tr valign="top">
                <th scope="row"><label for="dehum_mvp_ai_service_key"><?php _e('AI Service API Key', 'dehum-assistant-mvp'); ?></label></th>
                <td>
                    <?php $has_api_key = !empty(get_option('dehum_mvp_ai_service_key_encrypted')); ?>
                    <input type="password" id="dehum_mvp_ai_service_key" name="dehum_mvp_ai_service_key" value="" class="regular-text" placeholder="<?php echo $has_api_key ? esc_attr__('API key is set (enter new key to change)', 'dehum-assistant-mvp') : esc_attr__('Optional API key for authentication', 'dehum-assistant-mvp'); ?>" />
                    <p class="description">
                        <?php _e('Optional API key for authenticating with your AI service.', 'dehum-assistant-mvp'); ?>
                        <?php if ($has_api_key): ?>
                            <br><em><?php _e('API key is encrypted and stored securely. Leave blank to keep current key.', 'dehum-assistant-mvp'); ?></em>
                        <?php endif; ?>
                    </p>
                </td>
            </tr>
        </table>
        
        <!-- Legacy n8n Settings (Collapsible) -->
        <div class="dehum-legacy-settings" style="margin-top: 30px;">
            <h3 style="cursor: pointer;" onclick="toggleLegacySettings()">
                <?php _e('Legacy n8n Settings', 'dehum-assistant-mvp'); ?>
                <span style="font-size: 12px; color: #666;">(<?php _e('click to expand', 'dehum-assistant-mvp'); ?>)</span>
            </h3>
            <div id="legacy-settings-content" style="display: none;">
                <p style="color: #666; font-style: italic;"><?php _e('These settings are kept for backward compatibility. New installations should use the Python AI Service above.', 'dehum-assistant-mvp'); ?></p>
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
                            <?php $has_password = !empty(get_option('dehum_mvp_n8n_webhook_pass_encrypted')); ?>
                            <input type="password" id="dehum_mvp_n8n_webhook_pass" name="dehum_mvp_n8n_webhook_pass" value="" class="regular-text" placeholder="<?php echo $has_password ? esc_attr__('Password is set (enter new password to change)', 'dehum-assistant-mvp') : esc_attr__('Password', 'dehum-assistant-mvp'); ?>" />
                            <p class="description">
                                <?php _e('The Basic Auth password for your n8n webhook.', 'dehum-assistant-mvp'); ?>
                                <?php if ($has_password): ?>
                                    <br><em><?php _e('Password is encrypted and stored securely. Leave blank to keep current password.', 'dehum-assistant-mvp'); ?></em>
                                <?php endif; ?>
                            </p>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        
        <?php submit_button(); ?>
    </form>
    
    <script>
    function toggleLegacySettings() {
        var content = document.getElementById('legacy-settings-content');
        content.style.display = content.style.display === 'none' ? 'block' : 'none';
    }
    </script>
    
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
                    <label><?php _e('Search', 'dehum-assistant-mvp'); ?></label>
                    <input type="text" name="search" value="<?php echo esc_attr($filters['search']); ?>" placeholder="<?php esc_attr_e('Search messages, responses, or session ID...', 'dehum-assistant-mvp'); ?>">
                </div>
                
                <!-- Date Filter -->
                <div class="dehum-filter-field">
                    <label><?php _e('Date Range', 'dehum-assistant-mvp'); ?></label>
                    <select name="date_filter" onchange="toggleCustomDates(this.value)">
                        <option value=""><?php _e('All Time', 'dehum-assistant-mvp'); ?></option>
                        <option value="7_days" <?php selected($filters['date_filter'], '7_days'); ?>><?php _e('Last 7 Days', 'dehum-assistant-mvp'); ?></option>
                        <option value="30_days" <?php selected($filters['date_filter'], '30_days'); ?>><?php _e('Last 30 Days', 'dehum-assistant-mvp'); ?></option>
                        <option value="90_days" <?php selected($filters['date_filter'], '90_days'); ?>><?php _e('Last 90 Days', 'dehum-assistant-mvp'); ?></option>
                        <option value="custom" <?php selected($filters['date_filter'], 'custom'); ?>><?php _e('Custom Range', 'dehum-assistant-mvp'); ?></option>
                    </select>
                </div>
                
                <!-- IP Filter -->
                <div class="dehum-filter-field">
                    <label><?php _e('IP Address', 'dehum-assistant-mvp'); ?></label>
                    <input type="text" name="ip_filter" value="<?php echo esc_attr($filters['ip_filter']); ?>" placeholder="<?php esc_attr_e('Filter by IP...', 'dehum-assistant-mvp'); ?>">
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
                    <?php if ($filters['search'] || $filters['date_filter'] || $filters['ip_filter']): ?>
                        <a href="<?php echo admin_url('tools.php?page=dehum-mvp-logs'); ?>" class="button"><?php _e('Clear', 'dehum-assistant-mvp'); ?></a>
                    <?php endif; ?>
                </div>
            </div>
            
            <!-- Custom Date Range -->
            <div id="custom-dates" class="dehum-custom-dates" style="display: <?php echo $filters['date_filter'] === 'custom' ? 'block' : 'none'; ?>;">
                <div class="dehum-custom-dates-grid">
                    <div class="dehum-filter-field">
                        <label><?php _e('Start Date', 'dehum-assistant-mvp'); ?></label>
                        <input type="date" name="custom_start" value="<?php echo esc_attr($filters['custom_start']); ?>">
                    </div>
                    <div class="dehum-filter-field">
                        <label><?php _e('End Date', 'dehum-assistant-mvp'); ?></label>
                        <input type="date" name="custom_end" value="<?php echo esc_attr($filters['custom_end']); ?>">
                    </div>
                </div>
            </div>
        </form>
        
        <!-- Actions -->
        <div class="dehum-filter-actions">
            <div>
                <?php if ($total_sessions > 0): ?>
                    <a href="<?php echo wp_nonce_url(add_query_arg(['action' => 'export'] + $_GET), DEHUM_MVP_EXPORT_NONCE, 'export_nonce'); ?>" class="button">📊 <?php _e('Export Filtered Results', 'dehum-assistant-mvp'); ?></a>
                <?php endif; ?>
            </div>
            
            <div class="dehum-bulk-actions">
                <!-- Quick Delete Options -->
                <div class="quick-delete-actions">
                    <form method="POST" style="display: inline;" onsubmit="return confirm('<?php esc_attr_e('Delete conversations older than 90 days?', 'dehum-assistant-mvp'); ?>');">
                        <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                        <input type="hidden" name="bulk_action" value="delete_old">
                        <button type="submit" class="button button-secondary">🗑️ <?php printf(__('Delete Old (%d+ days)', 'dehum-assistant-mvp'), DEHUM_MVP_OLD_CONVERSATIONS_DAYS); ?></button>
                    </form>
                    
                    <button type="button" class="button" onclick="toggleAdvancedDelete()"><?php _e('More Delete Options', 'dehum-assistant-mvp'); ?></button>
                </div>
            </div>
        </div>
        
        <!-- Advanced Delete Options (Hidden by default) -->
        <div id="advanced-delete" class="dehum-advanced-delete" style="display: none;">
            <h3><?php _e('Advanced Delete Options', 'dehum-assistant-mvp'); ?></h3>
            <div class="advanced-delete-grid">
                <!-- Delete by Date Range -->
                <div class="delete-option">
                    <h4><?php _e('Delete by Date Range', 'dehum-assistant-mvp'); ?></h4>
                    <form method="POST" onsubmit="return confirm('<?php esc_attr_e('This will permanently delete all conversations in the selected date range. Continue?', 'dehum-assistant-mvp'); ?>');">
                        <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                        <input type="hidden" name="bulk_action" value="delete_by_date">
                        <div class="date-inputs">
                            <input type="date" name="delete_start_date" required>
                            <span><?php _e('to', 'dehum-assistant-mvp'); ?></span>
                            <input type="date" name="delete_end_date" required>
                        </div>
                        <button type="submit" class="button button-secondary"><?php _e('Delete Range', 'dehum-assistant-mvp'); ?></button>
                    </form>
                </div>
                
                <!-- Delete by IP -->
                <div class="delete-option">
                    <h4><?php _e('Delete by IP Address', 'dehum-assistant-mvp'); ?></h4>
                    <form method="POST" onsubmit="return confirm('<?php esc_attr_e('This will permanently delete all conversations from this IP address. Continue?', 'dehum-assistant-mvp'); ?>');">
                        <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                        <input type="hidden" name="bulk_action" value="delete_by_ip">
                        <input type="text" name="delete_ip" placeholder="192.168.1.1" pattern="^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$" required>
                        <button type="submit" class="button button-secondary"><?php _e('Delete IP', 'dehum-assistant-mvp'); ?></button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <?php if (empty($sessions)): ?>
        <div class="dehum-empty-state">
            <div class="empty-icon">💬</div>
            <h3><?php _e('No conversations found', 'dehum-assistant-mvp'); ?></h3>
            <p><?php _e('No conversations match your current filters. Try adjusting your search criteria.', 'dehum-assistant-mvp'); ?></p>
        </div>
    <?php else: ?>
        
        <!-- Results Info and Bulk Actions -->
        <div class="dehum-results-header">
            <div class="results-info">
                <?php 
                $start = (($current_page - 1) * $filters['per_page']) + 1;
                $end = min($current_page * $filters['per_page'], $total_sessions);
                printf(
                    __('Showing %d-%d of %d conversations', 'dehum-assistant-mvp'),
                    $start,
                    $end,
                    $total_sessions
                );
                ?>
            </div>
            
            <div class="bulk-actions-top">
                <form method="POST" id="bulk-delete-form" onsubmit="return confirmBulkDelete()">
                    <?php wp_nonce_field(DEHUM_MVP_BULK_NONCE, 'bulk_nonce'); ?>
                    <input type="hidden" name="bulk_action" value="delete_selected">
                    <select id="bulk-action-selector">
                        <option value=""><?php _e('Bulk Actions', 'dehum-assistant-mvp'); ?></option>
                        <option value="delete"><?php _e('Delete Selected', 'dehum-assistant-mvp'); ?></option>
                    </select>
                    <button type="submit" class="button" disabled id="bulk-apply-btn"><?php _e('Apply', 'dehum-assistant-mvp'); ?></button>
                </form>
                
                <div class="select-actions">
                    <button type="button" onclick="selectAllConversations(true)"><?php _e('Select All', 'dehum-assistant-mvp'); ?></button>
                    <button type="button" onclick="selectAllConversations(false)"><?php _e('Select None', 'dehum-assistant-mvp'); ?></button>
                </div>
            </div>
        </div>
        
        <!-- Instructions -->
        <div style="background: #e7f3ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #2271b1;">
            <strong>💡 How to use:</strong> 
            Click conversation cards to expand details • Use checkboxes for bulk actions • Click 🗑️ to delete individual conversations
        </div>
        
        <!-- Conversations List -->
        <div id="conversations-list">
            <?php foreach ($sessions as $session): ?>
                <div class="conversation-card" data-session="<?php echo esc_attr($session->session_id); ?>">
                    <div class="card-header">
                        <div class="conversation-checkbox">
                            <input type="checkbox" name="selected_sessions[]" value="<?php echo esc_attr($session->session_id); ?>" class="session-checkbox">
                        </div>
                        <div class="conversation-info">
                            <div class="conversation-preview"><?php echo esc_html(wp_trim_words($session->first_question, 12)); ?></div>
                            <div class="conversation-meta">
                                <span class="message-count"><?php echo intval($session->message_count); ?> exchange<?php echo intval($session->message_count) !== 1 ? 's' : ''; ?></span>
                                <span><?php echo human_time_diff(strtotime($session->last_message), current_time('timestamp')); ?> ago</span>
                                <span class="user-ip"><?php echo esc_html($session->user_ip); ?></span>
                            </div>
                        </div>
                        <div class="conversation-actions">
                            <button type="button" class="delete-session-btn" data-session="<?php echo esc_attr($session->session_id); ?>" title="<?php esc_attr_e('Delete this conversation', 'dehum-assistant-mvp'); ?>">🗑️</button>
                            <div class="expand-icon"><span class="dashicons dashicons-arrow-down-alt2"></span></div>
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
            <?php
            $base_url = admin_url('tools.php');
            $query_args = array_merge($_GET, ['page' => 'dehum-mvp-logs']);
            unset($query_args['paged']);
            
            $page_links = paginate_links([
                'base' => add_query_arg($query_args, $base_url) . '%_%',
                'format' => '&paged=%#%',
                'current' => $current_page,
                'total' => $total_pages,
                'prev_text' => '&laquo; ' . __('Previous', 'dehum-assistant-mvp'),
                'next_text' => __('Next', 'dehum-assistant-mvp') . ' &raquo;',
                'type' => 'plain',
                'end_size' => 2,
                'mid_size' => 2,
            ]);
            
            echo $page_links;
            ?>
        </div>
        <?php endif; ?>
        
    <?php endif; ?>
</div> 