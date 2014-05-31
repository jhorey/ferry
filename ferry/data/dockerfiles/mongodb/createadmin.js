/**
 * Create a new MongoDB adminstrator account. This script should be run
 * using the localhost exception. Once the adminstrator account is created
 * all future connections will be authenticated. 
 **/

db.createUser(
    {
	user: "LOGIN",
	pwd: "PASS",
	roles: [ "root" ]
    }
)