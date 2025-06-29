<?php
// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Class Dehum_MVP_Updater
 *
 * Simple GitHub-based update checker for the plugin.
 * Works as backup to GitHub Updater plugin.
 */
class Dehum_MVP_Updater {

    /**
     * Plugin file path
     */
    private $plugin_file;

    /**
     * Plugin slug
     */
    private $plugin_slug;

    /**
     * GitHub repository
     */
    private $github_repo;

    /**
     * Current version
     */
    private $current_version;

    /**
     * Constructor
     */
    public function __construct($plugin_file, $github_repo) {
        $this->plugin_file = $plugin_file;
        $this->plugin_slug = plugin_basename($plugin_file);
        $this->github_repo = $github_repo;
        $this->current_version = DEHUM_MVP_VERSION;

        // Only add hooks if GitHub Updater is not active
        if (!class_exists('Fragen\\GitHub_Updater\\Bootstrap')) {
            add_filter('pre_set_site_transient_update_plugins', [$this, 'check_for_updates']);
            add_filter('plugins_api', [$this, 'plugin_info'], 20, 3);
        }
    }

    /**
     * Check for plugin updates
     */
    public function check_for_updates($transient) {
        if (empty($transient->checked)) {
            return $transient;
        }

        // Get remote version
        $remote_version = $this->get_remote_version();
        
        if (version_compare($this->current_version, $remote_version, '<')) {
            $transient->response[$this->plugin_slug] = (object) [
                'slug' => dirname($this->plugin_slug),
                'plugin' => $this->plugin_slug,
                'new_version' => $remote_version,
                'url' => "https://github.com/{$this->github_repo}",
                'package' => "https://github.com/{$this->github_repo}/archive/main.zip"
            ];
        }

        return $transient;
    }

    /**
     * Get plugin information for update screen
     */
    public function plugin_info($result, $action, $args) {
        if ($action !== 'plugin_information') {
            return $result;
        }

        if (!isset($args->slug) || $args->slug !== dirname($this->plugin_slug)) {
            return $result;
        }

        $remote_version = $this->get_remote_version();
        $remote_readme = $this->get_remote_readme();

        return (object) [
            'name' => 'Dehumidifier Assistant MVP',
            'slug' => dirname($this->plugin_slug),
            'version' => $remote_version,
            'author' => 'Your Name',
            'homepage' => "https://github.com/{$this->github_repo}",
            'short_description' => 'AI-powered dehumidifier assistant with n8n integration.',
            'sections' => [
                'description' => $remote_readme,
                'changelog' => $this->get_changelog()
            ],
            'download_link' => "https://github.com/{$this->github_repo}/archive/main.zip"
        ];
    }

    /**
     * Get remote version from GitHub releases
     */
    private function get_remote_version() {
        $transient_key = 'dehum_mvp_remote_version';
        $cached_version = get_transient($transient_key);

        if ($cached_version !== false) {
            return $cached_version;
        }

        $url = "https://api.github.com/repos/{$this->github_repo}/releases/latest";
        $response = wp_remote_get($url, ['timeout' => 10]);

        if (is_wp_error($response)) {
            return $this->current_version;
        }

        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        if (isset($data['tag_name'])) {
            $version = ltrim($data['tag_name'], 'v');
            set_transient($transient_key, $version, HOUR_IN_SECONDS);
            return $version;
        }

        return $this->current_version;
    }

    /**
     * Get remote README content
     */
    private function get_remote_readme() {
        $transient_key = 'dehum_mvp_remote_readme';
        $cached_readme = get_transient($transient_key);

        if ($cached_readme !== false) {
            return $cached_readme;
        }

        $url = "https://raw.githubusercontent.com/{$this->github_repo}/main/dehum-assistant-mvp/README.md";
        $response = wp_remote_get($url, ['timeout' => 10]);

        if (is_wp_error($response)) {
            return 'Unable to fetch README from GitHub.';
        }

        $readme = wp_remote_retrieve_body($response);
        set_transient($transient_key, $readme, DAY_IN_SECONDS);
        
        return $readme;
    }

    /**
     * Get changelog from README
     */
    private function get_changelog() {
        $readme = $this->get_remote_readme();
        
        // Extract changelog section
        if (preg_match('/## 📝 Changelog(.*?)##/s', $readme, $matches)) {
            return trim($matches[1]);
        }
        
        return 'No changelog available.';
    }
} 