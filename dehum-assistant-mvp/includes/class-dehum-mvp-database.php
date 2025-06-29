<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Class Dehum_MVP_Database
 *
 * Handles all database interactions for the Dehumidifier Assistant MVP plugin.
 * This includes table creation, logging, querying, and data export.
 */
class Dehum_MVP_Database {

    /**
     * Get the name of the conversations table.
     *
     * @return string The full table name with the WordPress prefix.
     */
    public function get_conversations_table_name() {
        global $wpdb;
        return $wpdb->prefix . 'dehum_conversations';
    }

    /**
     * Create the conversations table on plugin activation.
     * Schema: id, session_id, message, response, user_ip, timestamp
     */
    public function create_conversations_table() {
        global $wpdb;
        
        $table_name = $this->get_conversations_table_name();
        $charset_collate = $wpdb->get_charset_collate();
        
        $sql = "CREATE TABLE $table_name (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
            session_id varchar(255) NOT NULL,
            message text NOT NULL,
            response text NOT NULL,
            user_ip varchar(45) DEFAULT NULL,
            timestamp datetime DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            KEY session_id (session_id),
            KEY timestamp (timestamp),
            KEY user_ip (user_ip),
            KEY session_timestamp (session_id, timestamp),
            KEY ip_timestamp (user_ip, timestamp),
            KEY timestamp_session (timestamp, session_id),
            FULLTEXT KEY search_content (message, response)
        ) $charset_collate;";
        
        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
        dbDelta($sql);
        
        update_option('dehum_mvp_db_version', '1.1');
        
        // Ensure composite indexes exist for existing installations
        $this->add_composite_indexes();
    }

    /**
     * Add composite indexes to existing table if they don't exist.
     */
    private function add_composite_indexes() {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        // Check if composite indexes exist and add them if missing
        $indexes_to_add = [
            'session_timestamp' => 'session_id, timestamp',
            'ip_timestamp' => 'user_ip, timestamp', 
            'timestamp_session' => 'timestamp, session_id'
        ];
        
        foreach ($indexes_to_add as $index_name => $columns) {
            $index_exists = $wpdb->get_var($wpdb->prepare(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS 
                 WHERE table_schema = %s AND table_name = %s AND index_name = %s",
                DB_NAME, $table_name, $index_name
            ));
            
            if (!$index_exists) {
                $wpdb->query("ALTER TABLE $table_name ADD INDEX $index_name ($columns)");
            }
        }
    }

    /**
     * Log a conversation to the database.
     *
     * @param string $session_id   The unique session identifier.
     * @param string $user_message The message sent by the user.
     * @param string $ai_response  The response from the AI.
     * @param string $user_ip      The user's IP address.
     * @return bool True on success, false on failure.
     */
    public function log_conversation($session_id, $user_message, $ai_response, $user_ip) {
        global $wpdb;
        
        $table_name = $this->get_conversations_table_name();
        
        $result = $wpdb->insert(
            $table_name,
            [
                'session_id' => $session_id,
                'message'    => $user_message,
                'response'   => $ai_response,
                'user_ip'    => $user_ip,
                'timestamp'  => current_time('mysql')
            ],
            ['%s', '%s', '%s', '%s', '%s']
        );
        
        return $result !== false;
    }

    /**
     * Get a paginated list of conversation sessions based on filter criteria.
     *
     * @param array $filters An associative array of filters (search, date_filter, etc.).
     * @return array An array of session objects.
     */
    public function get_sessions($filters = []) {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();

        list($where_clause, $where_params) = $this->build_where_clause($filters);

        $per_page = isset($filters['per_page']) ? intval($filters['per_page']) : DEHUM_MVP_DEFAULT_PER_PAGE;
        $paged = isset($filters['paged']) ? intval($filters['paged']) : 1;
        $offset = ($paged - 1) * $per_page;
        
        $session_query = "
            SELECT 
                session_id,
                COUNT(*) as message_count,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message,
                user_ip,
                MIN(message) as first_question
            FROM $table_name 
            $where_clause
            GROUP BY session_id 
            ORDER BY last_message DESC 
            LIMIT %d OFFSET %d
        ";
        
        $query_params = array_merge($where_params, [$per_page, $offset]);
        return $wpdb->get_results($wpdb->prepare($session_query, $query_params));
    }

    /**
     * Count the total number of sessions based on filter criteria.
     *
     * @param array $filters An associative array of filters.
     * @return int The total number of sessions.
     */
    public function count_sessions($filters = []) {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        list($where_clause, $where_params) = $this->build_where_clause($filters);
        
        $count_query = "SELECT COUNT(DISTINCT session_id) FROM $table_name $where_clause";

        if (!empty($where_params)) {
            return (int) $wpdb->get_var($wpdb->prepare($count_query, $where_params));
        } else {
            return (int) $wpdb->get_var($count_query);
        }
    }
    
    /**
     * Get detailed messages for a specific session ID.
     *
     * @param string $session_id The session ID.
     * @return array An array of message objects.
     */
    public function get_session_details($session_id) {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        return $wpdb->get_results($wpdb->prepare(
            "SELECT id, message, response, timestamp, user_ip 
             FROM $table_name 
             WHERE session_id = %s 
             ORDER BY timestamp ASC",
            $session_id
        ));
    }

    /**
     * Get statistics for the dashboard widget and admin header.
     *
     * @return array An associative array of stats.
     */
    public function get_stats() {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        $total_messages = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
        $total_sessions = $wpdb->get_var("SELECT COUNT(DISTINCT session_id) FROM $table_name");
        
        $today_messages = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM $table_name WHERE DATE(timestamp) = %s", 
            current_time('Y-m-d')
        ));
        
        $this_week_messages = $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM $table_name WHERE timestamp >= %s", 
            date('Y-m-d', strtotime('monday this week'))
        ));

        $latest_conversation = $wpdb->get_row("SELECT * FROM $table_name ORDER BY timestamp DESC LIMIT 1");

        return [
            'total_messages'      => (int) $total_messages,
            'total_sessions'      => (int) $total_sessions,
            'today_messages'      => (int) $today_messages,
            'this_week_messages'  => (int) $this_week_messages,
            'latest_conversation' => $latest_conversation,
        ];
    }
    
    /**
     * Delete conversations older than the configured number of days.
     *
     * @return int|false The number of rows deleted, or false on error.
     */
    public function delete_old_conversations() {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        return $wpdb->query($wpdb->prepare("
            DELETE FROM $table_name 
            WHERE timestamp < DATE_SUB(NOW(), INTERVAL %d DAY)
        ", DEHUM_MVP_OLD_CONVERSATIONS_DAYS));
    }

    /**
     * Export conversations to a CSV file.
     *
     * @param array $filters Filters to apply to the export.
     */
    public function export_conversations($filters = []) {
        global $wpdb;
        $table_name = $this->get_conversations_table_name();
        
        list($where_clause, $where_params) = $this->build_where_clause($filters);
        
        $query = "SELECT * FROM $table_name $where_clause ORDER BY timestamp DESC";

        if (!empty($where_params)) {
            $conversations = $wpdb->get_results($wpdb->prepare($query, $where_params));
        } else {
            $conversations = $wpdb->get_results($query);
        }

        // Generate filename and set headers
        $filename = 'dehumidifier-conversations-' . date('Y-m-d-H-i-s') . '.csv';
        header('Content-Type: text/csv');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Pragma: no-cache');
        header('Expires: 0');

        $output = fopen('php://output', 'w');
        
        fputcsv($output, ['Session ID', 'Date/Time', 'User Message', 'AI Response', 'User IP']);
        
        foreach ($conversations as $conv) {
            fputcsv($output, [$conv->session_id, $conv->timestamp, $conv->message, $conv->response, $conv->user_ip]);
        }
        
        fclose($output);
        exit;
    }

    /**
     * Build the WHERE clause for DB queries based on filters.
     *
     * @param array $filters An associative array of filters.
     * @return array An array containing the WHERE clause string and the parameters array.
     */
    private function build_where_clause($filters) {
        global $wpdb;
        $where_conditions = [];
        $where_params = [];
        
        // Search filter
        if (!empty($filters['search'])) {
            $search = $filters['search'];
            if (strlen($search) >= 3 && !preg_match('/[*%_]/', $search)) {
                $where_conditions[] = "MATCH (message, response) AGAINST (%s IN NATURAL LANGUAGE MODE)";
                $where_params[] = $search;
            } else {
                $where_conditions[] = "(message LIKE %s OR response LIKE %s)";
                $where_params[] = '%' . $wpdb->esc_like($search) . '%';
                $where_params[] = '%' . $wpdb->esc_like($search) . '%';
            }
        }
        
        // Date filter
        if (!empty($filters['date_filter'])) {
            switch ($filters['date_filter']) {
                case '7_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)";
                    break;
                case '30_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)";
                    break;
                case '90_days':
                    $where_conditions[] = "timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)";
                    break;
                case 'custom':
                    if (!empty($filters['custom_start'])) {
                        $where_conditions[] = "DATE(timestamp) >= %s";
                        $where_params[] = $filters['custom_start'];
                    }
                    if (!empty($filters['custom_end'])) {
                        $where_conditions[] = "DATE(timestamp) <= %s";
                        $where_params[] = $filters['custom_end'];
                    }
                    break;
            }
        }
        
        $where_clause = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';
        return [$where_clause, $where_params];
    }
} 