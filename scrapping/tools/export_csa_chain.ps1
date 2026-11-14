# Obtiene la cadena de CSA SOLO después de validación TLS de Windows.
# No instala certificados ni cambia la confianza del sistema.
$ErrorActionPreference = 'Stop'
$scrappingRoot = Split-Path -Parent $PSScriptRoot
$certificateDirectory = Join-Path $scrappingRoot 'certs'
$baselinePath = Join-Path $certificateDirectory 'windows-ca.pem'
if (-not (Test-Path -LiteralPath $baselinePath)) { throw 'Ejecuta primero python -m scrapping.tools.export_windows_ca' }
$serverName = 'donnees-data.asc-csa.gc.ca'
$client = New-Object System.Net.Sockets.TcpClient
$stream = $null
$chain = $null
try {
    $connection = $client.ConnectAsync($serverName, 443)
    if (-not $connection.Wait(15000)) { throw 'Timeout de conexión TLS' }
    $stream = New-Object System.Net.Security.SslStream($client.GetStream(), $false)
    $stream.ReadTimeout = 30000
    $stream.WriteTimeout = 30000
    # Sin callback de aceptación: Windows verifica certificado y nombre del servidor.
    $stream.AuthenticateAsClient($serverName)
    $certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($stream.RemoteCertificate)
    $chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
    $chain.ChainPolicy.UrlRetrievalTimeout = [TimeSpan]::FromSeconds(15)
    if (-not $chain.Build($certificate)) { throw ('Cadena no validada: ' + ($chain.ChainStatus.StatusInformation -join ', ')) }
    $pem = Get-Content -Raw -LiteralPath $baselinePath
    $issuers = @()
    # No se convierte el certificado hoja del sitio en autoridad de confianza.
    for ($index = 1; $index -lt $chain.ChainElements.Count; $index++) {
        $issuer = $chain.ChainElements[$index].Certificate
        $encoded = [Convert]::ToBase64String($issuer.RawData, [Base64FormattingOptions]::InsertLineBreaks)
        $pem += "`n-----BEGIN CERTIFICATE-----`n$encoded`n-----END CERTIFICATE-----`n"
        $issuers += @{ subject = $issuer.Subject; thumbprint = $issuer.Thumbprint }
    }
    $bundlePath = Join-Path $certificateDirectory 'csa-verified-chain.pem'
    Set-Content -LiteralPath $bundlePath -Value $pem -Encoding ascii
    @{
        servidor = $serverName
        validacion = 'SslStream con validacion predeterminada + X509Chain.Build exitoso'
        fecha_utc = [DateTime]::UtcNow.ToString('o')
        emisores = $issuers
        sha256 = (Get-FileHash -LiteralPath $bundlePath -Algorithm SHA256).Hash
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $certificateDirectory 'csa-verified-chain.json') -Encoding utf8
    Write-Output "Cadena TLS verificada; bundle: $bundlePath"
} finally {
    if ($chain) { $chain.Dispose() }
    if ($stream) { $stream.Dispose() }
    $client.Dispose()
}
