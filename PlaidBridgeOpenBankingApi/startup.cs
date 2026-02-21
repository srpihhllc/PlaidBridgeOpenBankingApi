public void ConfigureServices(IServiceCollection services)
{
    services.AddDbContext<TodoContext>(opt =>
       opt.UseSqlServer(Configuration.GetConnectionString("TodoContext")));
    services.AddControllers();
}
