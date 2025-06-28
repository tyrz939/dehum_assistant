# Test script for n8n webhook connection (PowerShell version)
# This tests the exact same connection that the WordPress plugin is trying to make

Write-Host "Testing n8n webhook connection..." -ForegroundColor Yellow
Write-Host "URL: http://localhost:5678/webhook/dehum-chat"
Write-Host "Username: dehum"
Write-Host "Password: LurINHgygtCjHJKIjnms"
Write-Host ""

# Create the Basic Auth header
$username = "dehum"
$password = "LurINHgygtCjHJKIjnms"
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(("{0}:{1}" -f $username, $password)))

# Prepare the request
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Basic $base64AuthInfo"
}

$body = @{
    message = "Hello from PowerShell test script"
} | ConvertTo-Json

$url = "http://localhost:5678/webhook/dehum-chat"

Write-Host "Sending request..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri $url -Method POST -Headers $headers -Body $body -Verbose
    Write-Host ""
    Write-Host "✅ SUCCESS!" -ForegroundColor Green
    Write-Host "Response received:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 3
} catch {
    Write-Host ""
    Write-Host "❌ ERROR:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    if ($_.Exception.Response) {
        Write-Host "HTTP Status Code: $($_.Exception.Response.StatusCode)" -ForegroundColor Red
        Write-Host "Status Description: $($_.Exception.Response.StatusDescription)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== RESULTS INTERPRETATION ===" -ForegroundColor Cyan
Write-Host "✅ SUCCESS: If you see a JSON response with 'success: true'" -ForegroundColor Green
Write-Host "❌ 401 Unauthorized: Username or password is wrong" -ForegroundColor Red
Write-Host "❌ 404 Not Found: Webhook URL is wrong or n8n workflow not active" -ForegroundColor Red
Write-Host "❌ Connection refused: n8n server is not running or wrong port" -ForegroundColor Red
Write-Host "❌ Could not resolve host: URL/hostname is wrong" -ForegroundColor Red 