// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {HYQUBRegistry} from "../src/HYQUBRegistry.sol";
import {HYQUBWallet} from "../src/HYQUBWallet.sol";
import {EntryPoint} from "account-abstraction/core/EntryPoint.sol";

contract DeployHYQUB is Script {
    // The real HYQUB backend approval-signer address, confirmed to
    // match test/ApprovalSignature.t.sol's EXPECTED_SIGNER constant.
    address constant APPROVAL_SIGNER =
        0x11c1293F62eA90Bf1d27490Fd17DD77C8fAD0CDD;

    function run()
        external
        returns (HYQUBRegistry, EntryPoint, HYQUBWallet)
    {
        vm.startBroadcast();

        HYQUBRegistry registry = new HYQUBRegistry();
        EntryPoint entryPoint = new EntryPoint();

        HYQUBWallet wallet = new HYQUBWallet(
            address(registry),
            APPROVAL_SIGNER,
            address(entryPoint)
        );

        vm.stopBroadcast();

        console.log("HYQUBRegistry deployed to:", address(registry));
        console.log("EntryPoint deployed to:", address(entryPoint));
        console.log("HYQUBWallet deployed to:", address(wallet));

        return (registry, entryPoint, wallet);
    }
}
