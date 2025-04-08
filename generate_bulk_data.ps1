$totalRecords = 1000
$batchSize = 100
$batches = [Math]::Ceiling($totalRecords / $batchSize)
$recordsCreated = 0

Write-Host "Generating $totalRecords records in $batches batches..."

for ($i = 0; $i -lt $batches; $i++) {
    $remainingRecords = $totalRecords - $recordsCreated
    $currentBatchSize = [Math]::Min($batchSize, $remainingRecords)
    
    Write-Host "Batch $($i + 1): Generating $currentBatchSize records..."
    
    $response = Invoke-RestMethod `
        -Uri 'http://localhost:5000/api/bulk/generate' `
        -Method Post `
        -Headers @{"Content-Type"="application/json"} `
        -Body "{`"count`": $currentBatchSize}"
    
    $recordsCreated += $currentBatchSize
    Write-Host "Progress: $recordsCreated/$totalRecords records created"
}

Write-Host "Done! Created $recordsCreated records in total."
