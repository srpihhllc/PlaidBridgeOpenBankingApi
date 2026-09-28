#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/health_check.py

import click


@click.command()
def health_check():
    """Check application health via test client."""
    from app import create_app
    
    app = create_app()
    client = app.test_client()
    
    response = client.get('/api/v1/health')
    
    click.echo(f"Status Code: {response.status_code}")
    click.echo(f"Response: {response.get_json()}")
    
    if response.status_code == 200:
        click.echo(click.style("✅ Health check PASSED", fg='green'))
    else:
        click.echo(click.style("❌ Health check FAILED", fg='red'))


if __name__ == '__main__':
    health_check()