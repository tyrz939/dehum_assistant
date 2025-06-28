<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}
?>
<div class="dehum-dashboard-stats">
    <div class="stats-grid">
        <div>
            <h4 class="stat-title"><?php _e('Total Activity', 'dehum-assistant-mvp'); ?></h4>
            <p class="stat-number">
                <?php echo number_format_i18n($stats['total_messages']); ?>
            </p>
            <small class="stat-description">
                <?php printf(
                    _n('%s session', '%s sessions', $stats['total_sessions'], 'dehum-assistant-mvp'),
                    number_format_i18n($stats['total_sessions'])
                ); ?>
            </small>
        </div>
        <div>
            <h4 class="stat-title"><?php _e('Recent Activity', 'dehum-assistant-mvp'); ?></h4>
            <p class="stat-number medium">
                <?php printf(
                    __('Today: %s', 'dehum-assistant-mvp'),
                    number_format_i18n($stats['today_messages'])
                ); ?>
            </p>
            <small class="stat-description">
                <?php printf(
                    __('This week: %s', 'dehum-assistant-mvp'),
                    number_format_i18n($stats['this_week_messages'])
                ); ?>
            </small>
        </div>
    </div>

    <?php if ($stats['latest_conversation']): $latest = $stats['latest_conversation']; ?>
        <div class="latest-conversation">
            <h4 class="conversation-title"><?php _e('Latest Conversation', 'dehum-assistant-mvp'); ?></h4>
            <p><strong><?php _e('User:', 'dehum-assistant-mvp'); ?></strong> <?php echo esc_html(wp_trim_words($latest->message, 12)); ?></p>
            <p><strong><?php _e('Assistant:', 'dehum-assistant-mvp'); ?></strong> <?php echo esc_html(wp_trim_words($latest->response, 12)); ?></p>
            <small>
                <?php printf(
                    __('%s ago', 'dehum-assistant-mvp'),
                    human_time_diff(strtotime($latest->timestamp), current_time('timestamp'))
                ); ?>
            </small>
        </div>
    <?php endif; ?>

    <p class="view-all-link">
        <a href="<?php echo admin_url('tools.php?page=dehum-mvp-logs'); ?>" class="button button-primary">
            <?php _e('View All Conversations', 'dehum-assistant-mvp'); ?>
        </a>
    </p>
</div> 