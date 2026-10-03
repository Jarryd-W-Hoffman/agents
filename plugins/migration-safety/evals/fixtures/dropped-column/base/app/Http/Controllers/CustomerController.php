<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreCustomerRequest;
use App\Models\Customer;

class CustomerController extends Controller
{
    public function show(Customer $customer): array
    {
        return [
            'id' => $customer->id,
            'name' => $customer->name,
            'email' => $customer->legacy_email ?? $customer->email,
        ];
    }

    public function store(StoreCustomerRequest $request): Customer
    {
        return Customer::create([
            'name' => $request->input('name'),
            'email' => $request->input('email'),
            'legacy_email' => $request->input('email'),
        ]);
    }
}
