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
            'name' => str($customer->name)->title(),
            'email' => $customer->email,
        ];
    }

    public function store(StoreCustomerRequest $request): Customer
    {
        return Customer::create([
            'name' => $request->input('name'),
            'email' => $request->input('email'),
        ]);
    }
}
