# Admin User Setup Guide

## Overview

This guide walks you through setting up an admin user for the FloodSense LK system. The authentication system uses Clerk, and admin users are synced to the PostgreSQL database with the `admin` role.

---

## Prerequisites

1. **Clerk Account** - User must already exist in your Clerk dashboard
2. **Backend Access** - You have access to the backend database and Python environment
3. **Database Migration Applied** - The `0003_users_table` migration has been run

---

## Step 1: Create User in Clerk Dashboard

1. Go to your Clerk Dashboard (https://dashboard.clerk.com)
2. Navigate to **Users** section
3. Click **Create User** or use an existing user
4. Fill in the user details:
   - **Email**: admin@flodsense.lk (or your preferred email)
   - **First Name**: Admin
   - **Last Name**: User
   - **Password**: [Set a strong password]

5. Click **Create**

6. Note the **User ID** (format: `user_XXXXXXXxxxxx`) - you'll need this in the next step

---

## Step 2: Apply Database Migration

Run the migration to create the users table if not already done:

```bash
cd flood-backend
alembic upgrade head
```

This creates the `users` table that stores synced user data.

---

## Step 3: Set Admin Role via Script

Use the admin setup script to promote the user to admin role in the database:

```bash
cd flood-backend
python scripts/setup-admin-user.py user_2abc123xyz admin@flodsense.lk "Admin User"
```

**Parameters:**
- `user_2abc123xyz` - Clerk User ID
- `admin@flodsense.lk` - Email address
- `"Admin User"` - Full name

**Expected Output:**
```
Setting up admin user...
Clerk ID: user_2abc123xyz
Email: admin@flodsense.lk
Name: Admin User

✅ Admin user created/updated successfully!
   Clerk ID: user_2abc123xyz
   Email: admin@flodsense.lk
   Name: Admin User
   Role: admin
```

---

## Step 4: Set Role in Clerk (Important!)

For the JWT token to include the admin role, you must also set the public metadata in Clerk:

1. Go to Clerk Dashboard → **Users**
2. Click on the admin user
3. Scroll to **Public metadata**
4. Set the following JSON:

```json
{
  "role": "admin"
}
```

5. Click **Save**

---

## Step 5: Test the Login

### Frontend:
1. Navigate to http://localhost:3000/sign-in
2. Sign in with the admin email and password
3. You should be redirected to the dashboard
4. Click the profile dropdown in the top-right
5. Verify your role shows as "admin"

### Backend (API):
```bash
# Get the auth token from frontend (check localStorage)
CLERK_TOKEN="your_clerk_jwt_token_here"

# Test admin endpoint
curl -H "Authorization: Bearer $CLERK_TOKEN" \
  http://localhost:8000/api/rbac/admin-test

# Expected response: 200 OK
# {"message": "Admin access granted"}
```

---

## Troubleshooting

### Issue: User shows as "citizen" role instead of "admin"

**Solution:**
1. Verify the public metadata is set in Clerk Dashboard
2. Re-run the setup script: `python scripts/setup-admin-user.py ...`
3. Clear browser cache and re-login
4. Check the Clerk JWT token includes: `"public_metadata": {"role": "admin"}`

### Issue: User cannot login

**Solution:**
1. Verify the user exists in Clerk Dashboard
2. Verify the users table migration has been applied: `psql -c "\\dt users"`
3. Check backend logs for webhook sync errors
4. Manually verify the user exists in database: `SELECT * FROM users WHERE email = 'admin@flodsense.lk';`

### Issue: Admin endpoints return 403 Forbidden

**Solution:**
1. Verify the Clerk JWT includes the admin role
2. Check backend logs: `docker logs flood-backend`
3. Verify the role-checking middleware is working
4. Re-run setup script and re-login

---

## Admin User Credentials

After completing the above steps, the admin user will have:

- **Email**: admin@flodsense.lk (or your chosen email)
- **Password**: [Your chosen password]
- **Clerk ID**: user_2abc123xyz (example)
- **Role**: admin
- **Database**: Synced in PostgreSQL `users` table

---

## Testing All Auth Flows

### 1. Sign In
- URL: http://localhost:3000/sign-in
- Use admin email and password
- Should redirect to dashboard

### 2. Sign Out
- Click profile dropdown (top-right)
- Click "Sign Out"
- Should redirect to sign-in page

### 3. Role-Based Access
- Admin role can access: `/api/rbac/admin-test`, all admin features
- Field Officer role can access: `/api/rbac/field-test`
- Citizen role can access: `/api/rbac/citizen-test`

---

## Reference

- **Clerk Docs**: https://clerk.com/docs
- **Role-Based Access Control**: See `app/auth/clerk.py`
- **Webhook Handler**: See `app/api/routers/webhooks.py`
- **Database Schema**: See `migrations/sql/0003_users_table.sql`
